# TOFshield Simulator - Instrument Configurator v0.3.9

Adds an integrated offline HTML User Guide in a separate, reusable window, with Markdown download and print/PDF options. The guide begins with objectives and covers all three panels, input meanings, the implemented peak/response/LOD/LOQ formulas, and an original animated instrument walkthrough with distinct Vocus and mipTOF routes and source links.

Imported acquisition fields are read-only in both panels. Unambiguous supported metadata is shown with provenance; missing/conflicting values are not replaced by demo defaults. The backend rejects instrument-response transformations on imported files. Display analysis and independently supplied calibration studies remain available. New simulation opens a fresh editable workspace. These are software safeguards, not filesystem permission changes.

Validation: 36 automated tests pass, including imported-data transform/export rejection, metadata absence/conflict handling, synthetic workflow availability, and existing spectrum/generator tests. Guide controls and Vocus/mipTOF animation routing were checked in the browser. External product pages are linked; the diagram is an original educational schematic, not verified vendor geometry.
