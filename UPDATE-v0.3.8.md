# v0.3.8

Adds Open in viewer buttons to the TOFWERK HDF5 assessment table. Each button opens the matching local HDF5 file read-only and switches to Spectrum Workspace. File metadata selects the instrument family; the reviewed assessment supplies the family when explicit metadata is unavailable. Unknown families clear the previous selection, and response models reset for each new file.

The endpoint accepts only paths listed in the assessment and respects the configured local roots, including symlink containment. Missing files produce an actionable message.

Validation: 30 automated tests pass, including path containment, missing files, instrument metadata precedence and assessment fallback.
