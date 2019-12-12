"""
Nowo Box Integration
"""
import logging
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA, ENTITY_IMAGE_URL)

from homeassistant.components.media_player.const import (SUPPORT_NEXT_TRACK, SUPPORT_PREVIOUS_TRACK, SUPPORT_TURN_ON, SUPPORT_SELECT_SOURCE, MEDIA_TYPE_CHANNEL, MEDIA_TYPE_TVSHOW)


from homeassistant.const import (STATE_OFF, STATE_ON, STATE_PLAYING)
from datetime import datetime

import homeassistant.helpers.config_validation as cv

import aiohttp
import asyncio

CONF_USERNAME = 'username'
CONF_PASSWORD = 'password'
CONF_FAVORITES = 'favorites'
CONF_SOURCE_FILTER = 'sourcefilter'


_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Nowo Box'
DEVICE_CLASS_TV = 'tv'
DOMAIN = 'nowo'

URL_SESSION = "https://api-nowotv.nowo.pt/api/v1/session"
URL_CHANNELS = "https://api-nowotv.nowo.pt/api/epg/v2/channel"
URL_SWIPE = "https://api-nowotv.nowo.pt/api/v1/swipe/action/"
URL_FAVORITE = "https://api-nowotv.nowo.pt/api/history/v1/favorite"
URL_EPG = "https://api-nowotv.nowo.pt/api/epg/v1/schedule/channel/{0}/from/{1}/until/{1}"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_FAVORITES, default=False): cv.boolean,
    vol.Optional(CONF_SOURCE_FILTER, default=[]): vol.All(cv.ensure_list, [cv.string])    
})

SUPPORT_NOWO = SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK | SUPPORT_TURN_ON | SUPPORT_SELECT_SOURCE 

async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    useFavorites = config.get(CONF_FAVORITES)
    sourceFilter = config.get(CONF_SOURCE_FILTER)

    async with aiohttp.ClientSession() as session:
        async with session.post(URL_SESSION, json={'type':'OTT','username': config[CONF_USERNAME],'password':config.get(CONF_PASSWORD),'device':{'alias':'web','properties':{'deviceOS':'Mac OS X','deviceOSVersion':'-','softwareVersion':'2.0.1'}}}) as resp:
            result = await resp.json();
    authorization = "Bearer " + result["id"]
    stbDevices = []
    stbs = result["properties"]["stbs"]
    for stb in stbs:
        if stb["type"] == "STB":
            newStb = NowoBoxTVDevice(authorization, stb, useFavorites, sourceFilter)
            await newStb.async_setup()
            stbDevices.append(newStb)
    async_add_devices(stbDevices)
    return True

class NowoBoxTVDevice(MediaPlayerDevice):
    """Representation of a NOWO BOX."""
    def __init__(self, authorization, stb, useFavorites, sourceFilter):
        self._stb = stb
        self._authorization = authorization
        self._useFavorites = useFavorites
        self._sourceFilter = sourceFilter

        self._unique_id = 'nowo.box' + stb["name"].lower()
        self._name = stb["name"]
        self._state = STATE_OFF
        self._device_class = DEVICE_CLASS_TV
        self._sources = []
        self._channels = []
        self._favoriteChannels = []
        self._currentChannel = None
        self._currentSourceIndex = -1
        self._currentEPG = None
        self._media_position_updated_at = None
        
    async def async_setup(self):
        sourceUrl = URL_CHANNELS if self._useFavorites else URL_FAVORITE

        async with aiohttp.ClientSession() as session:
            async with session.get(URL_CHANNELS, headers={'Authorization': self._authorization}) as resp:
                self._channels = await resp.json();
            async with session.get(URL_FAVORITE, headers={'Authorization': self._authorization}) as resp:
                self._favoriteChannels = await resp.json();
            
        for channel in self._channels:
            add = False
            if channel["enabled"]:
                add = True
                if self._useFavorites and  channel["id"] not in map(lambda favorite: favorite["id"], self._favoriteChannels):
                    add = False
                if len(self._sourceFilter) > 0 and len(list(filter(lambda filter: filter.upper() in channel["name"].upper(), self._sourceFilter))) == 0:
                    add = False
            if add:        
                self._sources.append(channel["name"])

    async def async_update(self):
        """Update TV info."""
        if self._currentChannel != None:
            async with aiohttp.ClientSession() as session:
                async with session.get(URL_EPG.format(self._currentChannel["id"], datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ")),  headers={'Authorization': self._authorization}) as epg:
                    self._currentEPG = await epg.json()
                    _start = datetime.strptime(self._currentEPG["schedules"][0]["published"]["start"], '%Y-%m-%dT%H:%M:%SZ')
                    _end = datetime.strptime(self._currentEPG["schedules"][0]["published"]["end"], '%Y-%m-%dT%H:%M:%SZ')
                    _duration = (_end -_start).total_seconds()
                    _current = (datetime.utcnow() - _start).total_seconds()
                    self._currentEPG["schedules"][0]["duration"] = _duration
                    self._currentEPG["schedules"][0]["current"] = _current
                    self._media_position_updated_at = datetime.utcnow()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID of the device."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_NOWO

    @property
    def media_content_type(self):
        """Content type of current playing media.
        Used for program information below the channel in the state card.
        """
        return MEDIA_TYPE_TVSHOW

    def turn_on(self):
        """Turn the media player on.
        Use a different command for Android as WOL is not working.
        """
        self._state = STATE_ON
    
    async def async_select_source(self, source):
        
        self._currentSourceIndex = self._sources.index(source)
        """Set the input source."""
        self._state = STATE_PLAYING
        self._currentChannel = list(filter(lambda channel: channel["name"] == source, self._channels))[0]
        async with aiohttp.ClientSession() as session:
            async with session.post(URL_SWIPE + self._stb["id"], json={'play':{'type':'CHANNEL', 'id': self._currentChannel["id"], 'bookmark': '0' }}, headers={'Authorization': self._authorization}) as resp:
                _LOGGER.debug(await resp.json())

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        if self._currentEPG != None:
            return self._currentEPG["schedules"][0]["duration"]
        return None

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        if self._currentEPG != None:
            return self._currentEPG["schedules"][0]["current"]
        return None

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        return self._media_position_updated_at

    @property
    def media_channel(self):
        """Channel currently playing."""
        if self._currentChannel == None:
            return None
        return self._currentChannel["name"]

    @property
    def media_title(self):
        """Title of current playing media."""
        if self._currentChannel == None:
            return None
        return self._currentChannel["name"]
    
    @property
    def media_series_title(self):
        """Title of series of current playing media, TV show only."""
        if self._currentEPG != None  and self._currentEPG["programs"] != None:
            return self._currentEPG["programs"][0]["title"]
        return None

    @property
    def media_season(self):
        """Season of current playing media, TV show only."""
        if self._currentEPG != None  and "seasons" in self._currentEPG and self._currentEPG["seasons"][0] != None:
            return self._currentEPG["seasons"][0]["season"]
        return None

    @property
    def media_episode(self):
        """Episode of current playing media, TV show only."""
        if self._currentEPG != None  and self._currentEPG["programs"] != None and "episode" in self._currentEPG["programs"][0] and self._currentEPG["programs"][0]["episode"] != 0:
            return "{0} {1}".format(self._currentEPG["programs"][0]["episode"], self._currentEPG["programs"][0]["episodeTitle"])
        return None


    @property
    def source(self):
        """Name of the current input source."""
        if self._currentChannel == None:
            return None
        return self._currentChannel["name"]

    @property
    def entity_picture(self): 
        """Image url of current playing media."""
        if self._currentEPG != None and "programs" in self._currentEPG and self._currentEPG["programs"] != None:
            return self._currentEPG["programs"][0]["posterImage"] + "?form=channel-square-1"
        if self._currentChannel == None:
            return None
        return self._currentChannel["squareLogo"] + "?form=channel-square-1"

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self._currentChannel == None:
            return None
        return self._currentChannel["squareLogo"] + "?form=channel-square-1"

    @property
    def device_class(self):
        """Return the device class of the media player."""
        return self._device_class
    
    @property
    def source_list(self):
        """List of available input sources."""
        return self._sources
        
        
    async def async_media_previous_track(self):
        """Send previous track command."""
        if self._currentSourceIndex >= 0:
            await self.async_select_source(self._sources[max(0, self._currentSourceIndex - 1)])

    async def async_media_next_track(self):
        """Send next track command."""
        await self.async_select_source(self._sources[min(self._currentSourceIndex + 1, len(self._sources) - 1)])
