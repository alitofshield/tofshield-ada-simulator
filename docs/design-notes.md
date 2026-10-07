# Viewer design notes

## Presentation patterns carried into the application

The reviewed 17-slide Vocus presentation repeatedly moves through three analytical levels:

1. A full mass-spectrum view establishes the overall chemical scene.
2. A selected mass window isolates a region of interest while preserving full-spectrum context.
3. A close peak view supports exact m/z reading and analyst annotation.

It also pairs spectra with time traces, experiment parameters, reagent-ion context, and quantitative tables. The viewer adopts the full-range → focused-window → peak-inspection hierarchy without embedding or reproducing the confidential presentation graphics.

## Application layout

### Left inspector

- File provenance and size
- Instrument and ionization metadata
- Environmental and geospatial metadata
- Acquisition timing and dimensions
- Mass-calibration parameters
- Searchable HDF5 group/dataset inventory
- Explicit structural and calibration warnings

### Right analysis stage

- Interactive amplitude/intensity-versus-m/z plot
- Full-spectrum range strip
- Drag, scroll, and numerical window controls
- Linear and logarithmic y-axis scales
- Sum/mean selection for multidimensional spectral data
- Peak table with click-to-focus behavior
- Current-window statistics
- PNG and CSV export

## Scientific boundaries

- Stored m/z values are displayed as provided.
- No formula is assigned from nominal mass alone.
- No peak is described as a validated compound detection.
- A missing calibrated axis is not reconstructed from guessed coefficients.
- The direct HDF5 reader can be replaced or supplemented by a TOFWERK Linux API adapter when the vendor shared libraries are available.

## Internal data flow

1. Validate the file signature and open the file read-only.
2. Inventory groups, datasets, attributes, shapes, types, units, chunks, and compression.
3. Categorize small metadata values by semantic key and HDF5 path.
4. Detect a stored spectrum and compatible mass axis, preferring standard TOFWERK paths.
5. Read only the requested x-window.
6. Aggregate earlier dimensions of multidimensional data while preserving the last sample dimension.
7. Apply min/max-envelope display reduction so narrow peaks survive downsampling.
8. Render the result locally with Plotly.js.

## Future production adapters

- Supported TOFWERK Linux `libtwh5.so` and `libtwtool.so` axis-generation adapter
- Write-specific dynamic calibration selection
- Chromatogram and selected-ion time-trace panel
- Measured-versus-fitted peak overlay
- Peak annotation with analyst-entered formula, adduct, isotope, ppm error, and confidence
- Session export containing file provenance, display range, plot, and analyst notes
