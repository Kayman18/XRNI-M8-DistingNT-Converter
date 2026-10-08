# XRNI → M8 / Disting NT Converter

Desktop utility for converting Renoise **.xrni** instruments into sample formats for the **Dirtywave M8** and **Expert Sleepers Disting NT**.

## Features

- **M8**: creates a sliced WAV with CUE markers and a companion slice map; select the XRNI velocity layer; optional mono conversion and peak normalization.
- **Disting NT Poly Multisample**: exports the mapped samples across all velocity layers, alongside a Poly Multisample JSON preset.
- **Disting NT WAV format**: 16-bit PCM, 44,100 Hz (resampled from the source where needed).
- **Piano preview**: C0–C9, with mapped notes highlighted.
- **Automatic output organization**: `Converted/M8/` or `Converted/Disting NT/` beside the launched application.

## Running from source

Requires **Python 3**, Tkinter, NumPy, and SoundFile:

```sh
python -m pip install -r requirements.txt
python xrni_to_m8_gui.py
```

For Linux, you may also need your distribution's Tkinter package (often `python3-tk`).

Use the platform launch scripts if included.

## Status

Development version. Disting NT JSON and sample loading should be verified on the target hardware; the WAV export targets 16-bit / 44.1 kHz. Standalone Windows and Linux executables are **not** included in the source package.

## Project files

- `xrni_to_m8_gui.py` — desktop UI
- `xrni_to_m8.py` — conversion logic
- `assets/` — GUI headers and Disting NT preset template

The repository is being initialized; converter source and assets will be uploaded separately.
