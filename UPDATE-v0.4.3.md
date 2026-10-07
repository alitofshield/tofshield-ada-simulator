# TOFshield Simulator - Instrument Configurator v0.4.3

- Reads TOFWERK EIT data from `/FullSpectra/TofData` shaped `(writes, ..., mass samples)`, including the observed `(360, 2, 40, 20736)` structure.
- Aggregates the intermediate stored spectra for each write while retaining the 360-write time dimension.
- Shows the complete expanded HDF5 inventory in the detached inspector.
- Find highlights the actual field; Previous and Next jump through matching fields without switching to a small result list.
- Adds a clear-search button and example search text.
