# Custom component for Nowo Tv Box using nowotv api
A platform which allows you to interact with the nowo box and can change the channel of the box

## Homekit TV supported
The media player will show up as Television accessories on devices running iOS 12.2 or later

## Configuration
**Example configuration.yaml:**

```yaml
media_player:
  - platform: nowo
    username: *******
    password: *******
    favorites: False
    sourcefilter:
      - FOX
      - AXN
      - CINE
      - DISNEY
```

**Configuration variables:**  
  
key | description  
:--- | :---  
**platform (Required)** | The platform name. (nowo)
**username (Required)** | The username used on nowotv.nowo.pt.
**password (Required)** | The password used on nowotv.nowo.pt.
**favorites  (Optional)** | A boolean indicate if you want to use your favorites channels only.
**sourcefilter (Optional)** | List of text that is used to filter the source list, eg. FOX will only show TV channels that name contains FOX

***
Due to how `custom_components` are loaded, it is normal to see a `ModuleNotFoundError` error on first boot after adding this, to resolve it, restart Home-Assistant.

***