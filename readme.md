# TOFshield Simulator - Instrument Configurator v0.4.6

Version 0.4.6 adds the production Cloudflare Container deployment. The public
online edition intentionally omits the private Team Share acquisition catalog;
authorized users can upload HDF5 and companion files for analysis during their
authenticated session.

Start with START-HERE.txt. The integrated User Guide describes current behavior; older release notes below describe earlier versions.

# TOFshield ADA HDF5 Viewer v0.3.7

Version 0.3.7 corrects instrument-context and state separation. It visibly identifies the detected instrument family, configures the interface for mipTOF by suppressing Vocus-only reagent controls, excludes generic analyte-type descriptions and LOD/LOQ study analytes from sample-target extraction, and removes every preloaded LOD/LOQ example value.

The Peak Inspector also reports estimated centroid m/z, baseline-corrected FWHM, resolving power and a measurement-quality classification. These values are calculated from the full selected-window data before display downsampling.

See UPDATE-v0.3.7.md for the state-isolation correction. Earlier update notes remain included for traceability.

# TOFshield ADA HDF5 Spectrum Explorer and Educational Generator

A local, read-only Ubuntu web application for examining HDF5 mass-spectrometry files. It inventories the file, groups available metadata into operator-friendly categories, and plots signal intensity against the stored mass-to-charge axis.

Version 0.2.0 adds explicitly synthetic educational HDF5 generation for Vocus CI-TOF and mipTOF scenarios. Generated files are intended for customer and partner demonstrations only; they are not measured TOFWERK data and are not validated for identification or quantification.

The first release is an exploratory viewer. It does not identify compounds, calculate a validated mass calibration, or replace TOFWERK acquisition and analysis software.

## What it does

- Correlates PDF, MAT, spreadsheet, table, note and configuration companion files with the active HDF5 run using explicit evidence.
- Searches HDF5 paths, dataset names, attributes, scalar values and embedded configuration text.
- Displays a time-resolved signal trace for a selected m/z interval when the source dataset contains an acquisition dimension.
- Completely resets and unloads the active file session without restarting the server.
- Opens `.h5`, `.hdf5`, and `.hdf` files through a browser upload.
- Opens large local files directly by path without copying them.
- Prefers TOFWERK-style `/FullSpectra/MassAxis` and `/FullSpectra/SumSpectrum` datasets.
- Can sum or average a multidimensional `/FullSpectra/TofData` dataset along its last (sample) axis.
- Inventories groups, datasets, shapes, types, compression, units, and small scalar values.
- Organizes attributes and small datasets into instrument, environment/location, acquisition, and calibration panels.
- Provides full-spectrum context, box zoom, scroll zoom, pan, logarithmic or linear y-axis, exact numeric range loading, peak navigation, PNG export, and CSV export.
- Uses peak-preserving min/max envelope reduction for responsive display of long spectra.
- Runs locally with no cloud dependency.
- Generates downloadable Vocus CI-TOF educational HDF5 files from a supported reagent ion, selected targets, and an environmental matrix.
- Generates downloadable mipTOF educational HDF5 files from selected isotopes and elemental/environmental background entries.
- Opens each generated HDF5 immediately in the same interactive viewer.

## Ubuntu 24.04 setup

Install the basic Python tooling once:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip
```

From this application folder:

```bash
chmod +x run.sh
./run.sh
```

If the application folder is stored on an NTFS or exFAT external drive, the launcher automatically keeps its Python virtual environment under `~/.virtualenvs/tofshield-hdf5-viewer`, where Linux symbolic links are supported.

To start the server and open the browser automatically:

```bash
chmod +x start-viewer.sh
./start-viewer.sh
```

Open this exact address in Firefox or Chrome:

```text
http://127.0.0.1:8081
```

The first launch creates `.venv` and installs the three Python dependencies listed in `requirements.txt`.

## Recommended setup for the TOFshield Team Share

The viewer allows files under the current Linux user's home folder, `/media`, and `/mnt` by default. To restrict direct-path access to the HDF5 area of Team Share, set an explicit root before starting:

```bash
export ADA_HDF5_ROOTS="/media/sali/ADA/TOFshield_Team_Share/HDF5"
./run.sh
```

Multiple roots use the Linux colon separator:

```bash
export ADA_HDF5_ROOTS="/media/sali/ADA/TOFshield_Team_Share/HDF5:$HOME/hdf5-test-data"
./run.sh
```

To use another port:

```bash
export ADA_VIEWER_PORT=8085
./run.sh
```

The server binds only to `127.0.0.1` unless `ADA_VIEWER_HOST` is deliberately changed.

## Loading data

## Generating educational HDF5 simulations

Use the **Vocus CI-TOF** or **mipTOF** tab in the left panel.

The Vocus generator supports the supplied reagent-ion choices and a curated selection of explosives, narcotics, cannabinoids, toxic industrial chemicals, VOCs, a spore-associated marker, and a chemical-agent simulant. A molecular formula can also be entered as a custom target. Its ion/adduct behavior and response values are deliberately simplified.

The mipTOF generator accepts supported isotope selections and environmental elements or compounds. Entered compounds are treated as atomized plasma inputs; the generated spectrum represents elemental ions rather than intact molecular ions.

Every generated file contains:

- `/FullSpectra/MassAxis`
- `/FullSpectra/SumSpectrum`
- `/FullSpectra/TofData`
- instrument, environment, and acquisition metadata
- synthetic annotation datasets
- explicit provenance and limitation records

Select **Download generated HDF5** to save the file after generation.

### Direct local path — recommended for large TOFWERK files

1. Start the viewer.
2. Paste the absolute file path, such as `/media/sali/ADA/TOFshield_Team_Share/HDF5/example.h5`.
3. Select **Open**.

The file is read in place and is never modified.

### Browser upload

Drop an HDF5 file into the upload area or select it with the file picker. Uploaded files are copied to:

```text
~/.cache/tofshield-ada-hdf5-viewer/uploads
```

The default upload ceiling is 2,048 MiB. Change it only when necessary:

```bash
export ADA_VIEWER_MAX_UPLOAD_MB=4096
```

### Synthetic example

Select **Open synthetic example** to verify the interface before using measured data. The fixture is visibly labeled synthetic and does not assert any chemical identity.

## How spectrum detection works

The viewer searches numeric HDF5 datasets in this priority order:

1. `/FullSpectra/SumSpectrum` with `/FullSpectra/MassAxis`.
2. Other one-dimensional spectrum/intensity datasets paired with a compatible one-dimensional mass or m/z axis.
3. Multidimensional TOF/spectrum datasets whose last dimension matches a mass axis; the earlier dimensions can be summed or averaged.
4. A spectrum without a compatible axis is plotted against sample index and clearly flagged. It is not labeled as m/z.

The stored mass axis is displayed exactly as found. If `/FullSpectra/MassCalibration` exists, the interface warns that a static stored axis may not capture write-by-write drift.

## Interaction model

- Drag across the main plot to zoom into a mass interval.
- Shift-drag to pan.
- Use the mouse wheel to zoom around the cursor.
- Double-click to restore the current loaded window.
- Enter numeric **From** and **To** values and select **Load exact window** to reread that region at higher point density.
- Use **Full spectrum** to return to the complete mass range.
- Switch between linear and logarithmic signal scales.
- Click a peak-table row to center a close view on that peak.
- Use the plot toolbar camera to export a PNG.
- Use **Export window CSV** to export the current numeric window.

## TOFWERK API compatibility note

The supplied API SDK contains Windows `TwH5Dll.dll`, `TwToolDll.dll`, and `TofDaqDll.dll` libraries. Its Python wrappers look for Linux shared libraries named `libtwh5.so` and `libtwtool.so`, but those Linux binaries were not present in the inspected SDK package. This viewer therefore uses `h5py` to read standard HDF5 objects directly.

For production-equivalent TOFWERK axis handling on Ubuntu, request the supported x86_64 Linux builds of `libtwh5.so` and `libtwtool.so` from TOFWERK/Bruker. The intended vendor-API sequence is:

1. `TwGetH5Descriptor`
2. `TwGetSumSpectrumFromH5`
3. `TwGetSpecXaxisFromH5` with mass axis type `1`
4. Plot returned intensity against returned m/z values
5. `TwCloseH5`

That can later be added as an optional adapter without changing the web interface.

## Verification

Regenerate the included fixture and run the automated checks:

```bash
source .venv/bin/activate
python scripts/generate_fixture.py
python -m unittest discover -s tests -v
```

## Data-handling boundaries

- The viewer opens files read-only.
- It does not write attributes or datasets back into the source file.
- It does not infer a compound name from a peak.
- It does not claim detection, identification, concentration, or source attribution.
- Confidential HDF5 files should remain on approved local or mounted storage.
