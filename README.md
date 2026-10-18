# XRNI → M8 / Disting NT / Normalized XRNI Converter

<img width="1429" height="882" alt="image" src="https://github.com/user-attachments/assets/a8e187e7-adf2-4353-94ee-7de6bda04952" />



Desktop utility for converting Renoise **.xrni** WAV/FLAC Samples instruments into sample formats for the **Dirtywave M8** and **Expert Sleepers Disting NT**.

## Features

- **Dirty Wave M8**: creates a sliced WAV with CUE markers and a companion slice map; select the XRNI velocity layer; optional mono conversion and peak normalization.
- **Disting NT Poly Multisample**: exports the mapped samples across all velocity layers, alongside a Poly Multisample JSON preset.
- **Disting NT WAV format**: 16-bit PCM, 44,100 Hz (resampled from the source where needed).
- **Piano preview**: C0–C9, with mapped notes highlighted based on sampled Range.
- **XRNI – Normalize WAVs**: normalize each WAV independently while preserving instrument settings and every velocity layer.
- **Automatic output organization**: `Converted/M8/`, `Converted/Disting NT/`, or `Converted/XRNI/` beside the launched application.
- **Linux(sh) and Windows(bat) Executables**
- **Vibe Coded**

## Running from source

Requires **Python 3**, Tkinter, NumPy, and SoundFile:

```sh
python -m pip install -r requirements.txt
```

For Linux, you may also need your distribution's Tkinter package (often `python3-tk`).

Use the platform launch scripts if included.

## XRNI – Normalize WAVs

Select an instrument and choose **XRNI – Normalize WAVs**, then click
**Normalize WAVs → XRNI**. The result is saved separately as
`Converted/XRNI/<instrument>_normalized.xrni` beside the application.
Browse lets you choose another filename within that folder. Existing files,
including the original instrument, are never overwritten; choose a new name
when repeating an export.

Each WAV receives its own peak-normalization gain, shared across its channels
so the stereo balance is preserved. This changes relative loudness between
samples/velocity layers. M8's optional normalization still applies to the whole
joined output. M8-only controls are disabled in the other modes.

- Original sample rate, channel count, frame count and bit depth are retained.
- Supports little-endian RIFF PCM WAV (8/16/24/32-bit), float WAV (32/64-bit),
  and compatible WAVEX data. PCM peaks target the highest positive representable
  value; floating-point peaks target 1.0.
- Silent and empty WAVs remain byte-for-byte unchanged.
- Instrument XML (including mappings, velocity layers, names, loop settings,
  envelopes and effects), non-WAV samples and other archive contents remain
  byte-for-byte unchanged. WAV headers and ancillary chunks are retained too.
- Unsupported WAV containers/encodings or corrupt/non-finite audio produce a
  clear error without publishing a partial output. No implicit format conversion
  is performed. Atomic output publishing requires filesystem hard-link support
  (available on ordinary NTFS/ext4/APFS volumes).

## Tests

With the requirements installed, run:

```sh
python -m unittest discover -s tests -v
```

GUI tests need Tkinter and a display. For a headless Linux machine:

```sh
xvfb-run -a python -m unittest discover -s tests -v
```

Tests generate XRNI fixtures with note and velocity mappings, loops, silence,
FLAC and unrelated entries. They verify ZIP CRCs, unchanged XML and metadata,
format preservation, normalization, failure cleanup and overwrite protection.
The generated XRNI is reopened with the converter and every mapped layer is
decoded again. GUI tests exercise mode switching and all three export workers.
Opening in the Renoise application remains a manual compatibility check.
