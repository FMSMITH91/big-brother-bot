Geolocation Plugin for BigBrotherBot
====================================

Description
-----------
A [BigBrotherBot][B3] plugin which introduces geolocation capabilities. This plugin is meant to be used as subplugin 
since it doesn't provide commands or visual reaction to B3 events. The plugin intercepts new clients connection and
retrieve geolocation data using multiple data sources:

* [ipwho.is](https://ipwhois.io/documentation) (HTTPS, no API key, 1000 lookups per day)
* [ipapi.co](https://ipapi.co/api/) (HTTPS, no API key, 1000 lookups per day)
* `mmdb`: an offline country database in the MaxMind DB format that you supply (IPv4 and IPv6), such as
  [DB-IP IP to Country Lite](https://db-ip.com/db/download/ip-to-country-lite) (free, monthly, CC BY 4.0) or MaxMind
  GeoLite2 Country
* [MaxMind GeoIP](https://dev.maxmind.com/geoip/legacy/install/country/) (bundled offline database from 2015, IPv4
  and country only: the last resort)

The online services are only ever queried over HTTPS, so player IP addresses do not cross the internet in clear text.
They still receive the IP address of every player who connects. To choose the services and their order, list the
plugin in b3.ini with its configuration file (`geolocation: @conf/plugin_geolocation.ini`) and set `geolocators`:
`mmdb, maxmind` keeps every lookup on your machine.

### Offline country database (mmdb)
B3 never downloads it. To use DB-IP's free database:

1. Download `dbip-country-lite-YYYY-MM.mmdb.gz` from https://db-ip.com/db/download/ip-to-country-lite and check its
   SHA1 against the one on that page.
2. Unzip it to `~/.b3/dbip-country-lite.mmdb` (Windows: `%USERPROFILE%\.b3\dbip-country-lite.mmdb`), or set
   `mmdb_file` to where you put it.
3. Replace it every month or so: B3 logs the file and its build date at startup, and warns when it is over 90 days old.

IP Geolocation by [DB-IP](https://db-ip.com), licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). B3 does not include DB-IP data: the operator downloads it.

For plugin developers
---------------------
To notify other plugins of client geolocation being completed, two events are being fired:

* `EVT_CLIENT_GEOLOCATION_SUCCESS` : when the geolocation succeeds
* `EVT_CLIENT_GEOLOCATION_FAILURE` : when the geolocation fails

When the geolocation succeed a new attribute is added the the `b3.clients.Client` object: `location`. This attribute
will hold all the geolocation data the plugin could retrieve:
 
* `client.location.country` : the country name
* `client.location.region` : the region name
* `client.location.city` : the city name
* `client.location.cc` : the two letter country code
* `client.location.rc` : the two letter region code
* `client.location.isp` : the Internet Service Provider name
* `client.location.lat` : the latitude value
* `client.location.lon` : the longitude value
* `client.location.timezone` : the timezone string
* `client.location.zipcode` : the postal code

*NOTE #1* : when `EVT_CLIENT_GEOLOCATION_FAILURE` is fired `client.location` is set to `None`  
*NOTE #2* : when the plugin cannot retrieve a specific geolocation value, its attribute is set to `None`