# TOFshield Simulator - Instrument Configurator v0.4.2

- Keeps detached-window controls attached by reusing the already-loaded offline Plotly runtime rather than navigating the child document during binding.
- Restores Find, Previous, Next, category tabs, graph controls and Close in detached windows.
- Reads `NbrSamples`, `NbrWrites` and `NbrSegments` when stored as root-level HDF5 attributes.
- Shows the active HDF5 filename in detached windows.
