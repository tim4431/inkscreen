# Inkscreen

![Inkscreen](docs/demo.jpg)

# Features
- **Home Assistant**: Integrates with Home Assistant to display sensor data/status and refresh in real-time.
- **Timer**: E.g. generate temperature charts every 10 minutes.
- **Notebook**: Randomly keep some notes!

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
