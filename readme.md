# Inkscreen

![Inkscreen](docs/demo.jpg)

# Features
This inkscreen driver and rendering part of this project is based on the ![epdiy](https://github.com/vroland/epdiy) project.

This project uses inkscreen as a convenient tool to display quasi-static information, which support all-day-on display. I have implemented several components, including:

- **Home Assistant Entity Status**: Integrates with Home Assistant to display sensor data/status and refresh in real-time.
- **Timer**: E.g. generate temperature charts every 10 minutes.
- **Notebook**: Randomly keep some notes, such as cake recipes, to-do lists, etc.

You can design the block to be in **dark color** when something **worth paying attention to** happens, such as a sensor is unavailable or the sunset quality is >50% (which is quite rare in my area though!). Then when you take a glance at the screen, you can see the dark blocks and know something is worth checking.

# 3D model and hardware design
Please refer to the `hardware` folder

# Design and Structure


# Usage
Running from the command line:
Create a `secrets.yaml` in root folder using the template `secrets.example.yaml`.
Modify `config.yaml` according to your local ha settings.

```bash
pip install -r requirements.txt
python main.py
```

Running from docker:
```bash
docker build -t inkscreen .
docker compose up -d
```


# Configuration
