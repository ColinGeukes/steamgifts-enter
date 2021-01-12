# SteamGifts-enter
Simple automation to enter steamgifts giveaways, by using a chrome browser and a custom profile

## Configuration
To allow the application to run, we must set it up correctly.

### Profile
We must create a custom chrome profile, this is to ensure that you can run your normal chrome profile and allows the chrome driver to keep its logged in status.
After creation of the custom profile, open it and navigate to `chrome://version/`. Save the `profile path` as we need it in the next step, the config file.

### Config file
In the `root` of the project a `config.json` file must be created with the following information.
```json
{
  "chrome-profile-path": "C:\\Users\\___USER___\\AppData\\Local\\Google\\Chrome\\User Data\\___CUSTOM PROFILE___",
  "search": {
    "level_min": 2,
    "level_max": 8,
    "entry_min": 0,
    "entry_max": 5000,
    "point_min": 10,
    "point_max": 50,
    "rating_min": 60,
    "rating_max": 100
  }
}
```
The `chrome-profile-path` must direct to the custom chrome profile created for the application.

