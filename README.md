# Third Person Readable Maps

Render filled map contents on maps carried by players in third-person view.

## Features

- Display the map image on the carried map surface.
- Follow the player's existing hand movement.
- Support maps in either hand, with placement based on the occupied hands.
- Run on the client side.

## Requirements

- Minecraft 1.21.11
- Fabric Loader 0.18.1 or newer
- Java 21 or newer

## Installation

1. Install Fabric Loader for Minecraft 1.21.11.
2. Place `third-person-readable-maps.jar` in your Minecraft instance's `mods` directory.
3. Launch the Fabric profile and hold a filled map while using third-person view.

Your client must have received the map data before its contents can be displayed.

## Build from source

### Windows

With Java 21 or newer on `PATH`, run:

```bat
Build-Windows.bat
```

The script downloads Gradle 9.6.1 into `.gradle-local`, builds the project, and
copies `third-person-readable-maps.jar` to the project root.

### Other platforms

Install Java 21 or newer and Gradle 9.6.1, then run:

```sh
gradle --no-daemon build
```

The output is `build/libs/third-person-readable-maps.jar`.
Network access is required to download build dependencies.

## Project

- Repository: [skyRolly/third-person-readable-maps](https://github.com/skyRolly/third-person-readable-maps)
- Mod ID: `thirdpersonreadablemaps`
- Version: `0.0.1`
- Minecraft: `1.21.11`

## Report an issue

Use the [issue tracker](https://github.com/skyRolly/third-person-readable-maps/issues).
Include your Minecraft, Fabric Loader, Java, and mod versions, reproduction steps,
and the relevant client log.
