# TOFshield Simulator - Instrument Configurator

User Guide

Version 0.3.9 · First integrated guide · Runs locally with the application

The objective is to help you understand measured mass spectra and explore educational instrument scenarios in one place.

- Open an HDF5 measurement and inspect its spectrum, metadata and quality.
- Keep the original acquisition settings fixed when reviewing imported measurements.
- Start a separate simulation to explore reagent choices, targets and illustrative instrument responses.
- Understand each calculated peak value and the formula behind it.
- Review the 97 TOFWERK files by instrument and suitability for ADA development.
- Learn the path from sample introduction to ion detection through the animated walkthrough.

The application does not control hardware, identify unknown compounds automatically, or validate a detector or ML model. Simulated results are educational, and measured-file metadata may be incomplete.

Use the **User Guide** button in the application header to open this guide in a separate, resizable window. Click it again to focus the existing guide window. If a separate window is blocked, the browser can open a new tab instead. Place it beside the simulator to read while you work.

**Choose your workflow:** import a measurement for read-only acquisition review, or start a new simulation for editable demonstration settings. Analysis controls such as mass windows, aggregation and independently supplied calibration studies remain available for imported measurements.

## 1. Spectrum Workspace

### Contents

- File opening and the measured/simulated distinction
- Vocus and mipTOF input fields
- Spectrum controls, metadata and data quality
- Window statistics and peak calculations
- Fourier analysis

### Open a measurement or create a simulation

| Control | Purpose and expected content |
|---|---|
| Open HDF5 / Choose or drop a file | Opens an HDF5 file from your computer. Browser uploads use a local cache; large files are better opened directly by path or from the TOFWERK table. |
| Local Ubuntu path / Open | Absolute path to an HDF5 file within the configured read roots. The file is opened read-only, without making a large upload copy. |
| Open synthetic example | Opens the included, explicitly synthetic example. It is not Christian's measured data. |
| Vocus CI-TOF / mipTOF selectors | Select the synthetic generator when no measurement is locked. On import, the instrument family is synchronized from descriptive metadata or the reviewed table. The instrument selectors are locked until a new simulation is started. |
| Imported measurement · locked | Indicates that reagent, targets, matrix and acquisition configuration describe the selected file. Unavailable values say Not recorded; conflicting records say Multiple recorded values. The app does not fill these gaps with demo values or infer target identity from peaks. |
| New Vocus simulation / New mipTOF simulation | Starts a fresh editable workspace. It clears the currently open file from the workspace but does not modify that file. |
| Generate and view… | Creates a new synthetic HDF5 spectrum from your editable inputs. Available in simulation mode only. |
| Download generated HDF5 | Saves the newly generated synthetic file. The synthetic provenance remains explicit. |

### Vocus input fields

These fields are editable in a **new simulation** and read-only for an **imported file**. Recorded inputs are not laboratory-verified merely because they appear in HDF5 metadata.

| Field | Purpose | What it can contain |
|---|---|---|
| Reagent ion | Chooses the generator's simplified ion-formation rule. It cannot change the chemistry of an existing measured acquisition. | I−, NO3−, H3O+, NH4+, NO+ or O2+; type the supported software tokens I-, NO3-, H3O+, NH4+, NO+, O2+. |
| Targets | Names the compounds for an educational synthetic mixture. | Comma-separated supported library names such as ACETONE, BENZENE, or supported molecular formulas such as C3H6O. Invalid or unsupported formulas produce an error. |
| Add from forensic and safety library | Adds a predefined name/formula to Targets. | One of the listed substances. A library entry is not a validated reference spectrum or an identification result. |
| Environmental matrix | Supplies illustrative background components for the generator. | Comma-separated supported formulas, for example H2O, N2, O2, CO2. Imported values are shown only when the file records them unambiguously. |

The generator places simplified ions using its mass library: molecular mass is the sum of element counts × stored atomic masses, followed by the selected reagent shift. I−, NO3−, NH4+ and NO+ use the implemented adduct shifts; H3O+ adds a proton shift; O2+ uses the molecular mass in this simplified model. These are software rules, not predictions of fragmentation, competing reactions, selectivity or real sensitivity.

### mipTOF input fields

| Field | Purpose and expected content |
|---|---|
| Target isotopes | Comma-separated supported isotope keys or elements, for example Fe, Fe-56 or Pb-208. The synthetic output represents elemental/isotopic ions. |
| Add from isotope library | Adds one of the available isotope entries to the target list. |
| Environmental elements or compounds | Examples: N2, O2, Ar, Fe. The generator treats compounds as elemental contributions rather than intact molecular ions. |

### Spectrum display and navigation

| Item | Meaning and use |
|---|---|
| File name and provenance | Confirm which file is open and whether it is imported or synthetic before interpreting anything else. |
| Spectrum source | Selects the stored array and its mass axis. A stored SumSpectrum is already one-dimensional; TofData may combine many recorded spectra. |
| m/z axis | Mass-to-charge ratio in Th where a stored mass axis exists. A fallback sample index is not a calibrated mass axis. |
| Intensity axis | Signal in the dataset units, or arbitrary units when units are absent. Peak height does not directly establish concentration. |
| Aggregation: Sum / Mean | For M spectra: sum at mass bin i = Σ(j=1…M) y[j,i]; mean = sum/M. Disabled for an already one-dimensional source. |
| Linear / logarithmic Y scale | Changes presentation. Log scale shows small positive peaks beside large ones, but cannot normally display zero/negative values. |
| From / To and Load exact window | Restricts the analysis to a mass interval. Use it for detailed peak measurements, rather than relying on visual zoom alone. |
| Full spectrum / Reset view | Full spectrum reloads the full available analysis range; Reset view restores chart zoom. Neither is an instrument recalibration. |
| Drag, Shift + drag, double-click | Zoom, pan and reset the chart. The lower range strip preserves context. |
| Export window CSV | Saves the current analyzed window. A simulated response export contains transformed values; it is not an untouched source-file export. Large exports can be display-reduced to the application's point limit. |
| Parameters | Original metadata and recorded acquisition context. Consult these records when a form field is Not recorded or ambiguous. |
| Datasets and object search | HDF5 arrays, dimensions and paths. Search for MassAxis, PeakData, pressure or another object name. |
| Data quality | Viewer checks and warnings. A readable file or unflagged peak is not proof of chemical identification or validated detection performance. |

For the first listed Vocus file, `P8B-006_MCP_2024.02.12-15h21m35s_I-.h5`, the default source is `/FullSpectra/SumSpectrum` versus `/FullSpectra/MassAxis`: 20,736 bins spanning about 8.977–518.908 Th. It is a split derivative, with 720 stored spectra in TofData. Its reagent label in the filename is not automatically treated as recorded metadata. A 12-component mixture need not produce exactly 12 peaks.

### Window statistics — the actual formulas

Let x[i] be the mass coordinate and y[i] the finite analyzed intensity in the selected window; N is the number of those points. Statistics and peak calculations precede display reduction.

| Value | Formula / meaning |
|---|---|
| Raw points | N = number of analyzed mass-axis bins, not independent experiments or particles. |
| Maximum | max(y[i]). |
| Mean | Σ y[i] / N. |
| Total signal | Σ y[i]. This is a bin sum, not a mass-axis integral or a calibrated concentration. |
| Display reduction | A reduced set of points can be plotted for speed. This can affect visual inspection; exact-window reloads help inspect a region. |

### Peak inspector — strongest local maxima

The app selects local maxima satisfying y[i] > y[i−1] and y[i] ≥ y[i+1], sorts them by intensity, applies a minimum sample-index separation and keeps up to 20. If there are no local maxima, it can fall back to the largest sampled signal. This is a peak-picking rule, not compound identification.

For each peak, the implementation searches outward to the adjacent valleys. It uses baseline **b = max(left valley intensity, right valley intensity)**, peak height above baseline **h = y[peak] − b**, and half-height level **H = b + h/2**.

| Column | Formula and interpretation |
|---|---|
| # | Peak rank in the selected list. |
| Centroid m/z | Within the half-height boundaries: μ = Σ(x[i] × w[i]) / Σw[i], where w[i] = max(y[i] − b, 0). Falls back to the sampled peak position if a centroid cannot be calculated. |
| Intensity | y[peak], the signal at the selected local maximum; it is not baseline-subtracted integrated peak area. |
| FWHM (Th) | x[right half-height crossing] − x[left half-height crossing]. Each crossing uses linear interpolation: x₀ + ((H−y₀)/(y₁−y₀)) × (x₁−x₀). The fraction is clamped between 0 and 1; equal adjacent intensities use the midpoint. |
| Resolving power | R = μ / FWHM. It describes this estimated peak width, not the manufacturer's certified instrument resolution. |
| Peak quality | Estimated: the algorithm obtained a width with at least four sampled bins inside the half-height boundaries. Undersampled: fewer than four; a displayed numeric width is then poorly constrained. Truncated: boundary/crossing limitations. Overlapping: no usable isolated half-height construction. Unavailable/No mass axis: no supported estimate. |
| Concentration | With a matching calibration: C = max(0, (I−a)/S), where I is peak intensity, a is the calibration intercept and S its positive slope. It is not automatically available from a measured spectrum alone. |
| S/N | max(0, (I−mean blank)/σ) when a study supplies a positive σ. It is the app's study-based estimate, not an independent measure of every peak's local noise. |
| LOD/LOQ status | Only evaluated if abs(μ−quantifier m/z) ≤ tolerance and a usable study exists. See the formulas and status rules in Instrument Configuration below. |

An **Undersampled** badge means the software can display an estimate but too few bins define the width. Zooming cannot create missing acquisition samples. Use an exact mass window to inspect the data, but do not read the many displayed decimal places as measurement accuracy.

### Fourier & Fast Fourier Transform

The transform examines repetition along the mass axis, not the physical TOF waveform. It interpolates the displayed spectrum onto a uniform power-of-two grid; Direct DFT uses up to 1,024 points and FFT up to 8,192.

| Control or result | Formula / use |
|---|---|
| Remove mean | Subtract average intensity before the transform. |
| Apply Hann window | w[n] = 0.5 × (1 − cos(2πn/(N−1))). Without it, w[n] = 1. |
| Direct DFT / FFT | Both compute X[k] = Σ(n=0…N−1) s[n] exp(−2πikn/N), with s already mean-adjusted/windowed as selected. FFT uses a faster algorithm. Different grid sizes can give different displays. |
| Amplitude | abs(X[k])/Σw[n], doubled for positive bins except the Nyquist bin; DC and Nyquist are not doubled. Linear/logarithmic is a display choice. |
| Grid spacing | Δx = (last x − first x)/(N−1). |
| Frequency | f[k] = k/(N × Δx), in cycles/Th when x is m/z. |
| Dominant non-DC frequency | Highest-amplitude nonzero-frequency bin. |
| Equivalent spacing | 1/f[dominant], in Th/cycle. It is not detector frequency or flight time. |
| Calculation time | Elapsed transform computation time measured by the browser, in milliseconds. |

## 2. Instrument Configuration

### Contents

- Animated sample-to-detector walkthrough
- Recorded acquisition versus editable simulation
- Every configuration field and its effect
- Apply, reset and export controls
- Response-model equations
- LOD/LOQ inputs, calculations and limitations

### How the instrument works — animated walkthrough

<!-- INSTRUMENT_ANIMATION -->

Choose Vocus or mipTOF, then Play/Pause or Step. Select a stage for its explanation. The colored packets illustrate lower and higher m/z travelling through a simplified analyzer; timing, geometry and particle counts are not instrument specifications or the loaded file's actual acquisition.

**Vocus:** sample molecules enter a reaction region, where reagent ions form product ions through controlled chemical reactions. Ion optics deliver the ions to the TOF analyzer. Reactor/reagent choice affects which compounds can respond. Source: [TOFWERK Vocus](https://www.tofwerk.com/products/vocus/) and [reactors and core technologies](https://www.tofwerk.com/products/vocus/reactors-and-core-technologies/).

**mipTOF:** sampled particles enter a microwave-sustained plasma, which enables elemental-ion analysis. This route differs from Vocus molecular chemical ionization. Source: [TOFWERK mipTOF](https://www.tofwerk.com/products/miptof/).

**TOF principle:** after acceleration through a potential magnitude U, the idealized energy relation is qU = mv²/2 and a field-free path gives t = L√(m/(2qU)). Thus, at fixed conditions, flight time scales with √(m/q); lower m/z arrives earlier. A reflectron compensates energy spread. The actual instrument uses calibrated timing and more complex optics. Source: [JEOL mass-spectrometry basics](https://www.jeolusa.com/RESOURCES/Analytical-Instruments/Mass-Spectrometry-Basics).

This is an original educational schematic of the principles used by the TOFWERK instrument families reviewed in TOFshield. It is not a copied vendor animation, a manufacturer-endorsed model, or a verified hardware design for a separate TOFshield-built instrument.

### Recorded acquisition versus simulation settings

When an HDF5 file is imported, acquisition controls are locked across both panels. This includes reagent ion, target list, environmental matrix and the instrument-configuration form. The app shows unambiguous metadata where available; missing settings remain **Not recorded**, and conflicting values point to **Parameters**. It does not invent acquisition conditions from a file's peaks or a demo preset.

For editable settings, select **New Vocus simulation** or **New mipTOF simulation**. This clears the open measurement from the workspace and starts a separate educational scenario. The original HDF5 remains unchanged.

The form fields below describe the **simulation mode**. Modelled-effect fields alter the illustrative response; context-only fields document assumptions but do not change calculated intensity. They are not TOFWERK specifications. Vocus reagent-ion response modelling is disabled for mipTOF.

| Top control | Meaning |
|---|---|
| HDF5 instrument context | Family plus its evidence. Assessment-based classification is distinguished from direct metadata. No automatic compound identification is implied. |
| Apply illustrative response model | In simulation mode, enables selected transformations when Apply is pressed. Unchecked means the stored synthetic spectrum is analyzed without this extra transform. Disabled for imported data. |
| Reagent-ion mode | Sets the new Vocus generator's reagent rule. Changing it requires generating a new synthetic spectrum to change ion positions; it cannot re-ionize an existing spectrum. |
| Instrument state | With a simulated response enabled: Ready permits output; Standby/Fault sets the calculated signal to zero. It is not a hardware status reading. |

### Sampling inlet

| Field | Meaning and expected effect when applied |
|---|---|
| Sample flow (mL/min) | Together with inlet volume, determines the modelled transport delay. Higher flow shortens this delay; it is not a general flow-dependent sensitivity calculation. |
| Inlet volume (mL) | Larger volume increases the delay at the same flow. |
| Inlet temperature (°C) | Context only. No heating, adsorption or decomposition calculation is implemented. |
| Dilution factor | Divides the modelled signal. Increasing from 1 to 2 approximately halves the signal when the other effects remain unchanged. |
| Inlet loss (%) | Removes the entered fraction of signal. For example, 20% leaves 80% before the other model effects. |
| Carryover signal (a.u.) | Adds a constant residual-signal level across the spectrum. It does not simulate compound-specific memory peaks or time-dependent washout. |
| Time since sample arrival at inlet (s) | Evaluates the model's response at one elapsed time. This is not a time selector for the file's stored scans. |
| Response time constant (s) | Controls the modelled approach to steady response after the transport delay. A larger value gives a slower rise. |

The calculated delay is `60 × inlet volume / sample flow`, in seconds. With the defaults, 1 mL and 100 mL/min give **0.6 seconds**. The response fraction approaches 100% as elapsed time increases beyond that delay.

### Reagent-ion source

| Field | Meaning and expected effect |
|---|---|
| Reagent signal (relative to reference) | A multiplicative response factor: 1 is the reference, 2 doubles this contribution. It does not measure or solve reagent depletion and reaction chemistry. |

### Reaction chamber

| Field | Meaning and expected effect |
|---|---|
| Reaction pressure (mbar) | Context only; no pressure-dependent chemistry is calculated. |
| Reaction temperature (°C) | Context only; no temperature-dependent reaction kinetics are calculated. |
| Reaction time (ms) | Context only; does not calculate conversion or reaction yield. |
| Reduced field E/N (Td; PTR context) | Context only. Describes electric field relative to gas number density in a relevant PTR scenario; it is not a validated setting for every Vocus reagent mode. |
| Relative humidity (%) | Context only; changing it does not create water clusters or calculate humidity-dependent sensitivity. |
| Empirical reaction response multiplier | Scales intensity uniformly. Use it for an explicitly assumed response comparison, not as an independently calibrated sensitivity. |

### Ion transfer & vacuum

| Field | Meaning and expected effect |
|---|---|
| Analyzer vacuum (mbar) | Context only; no gas-collision or vacuum-performance calculation. |
| Ion transmission (%) | Scales the signal by the stated transmission fraction. |
| Transmission roll-off per 100 Th | Applies increasing attenuation at higher m/z. Zero means no additional mass-dependent attenuation. |

### TOF analyzer

| Field | Meaning and expected effect |
|---|---|
| Minimum m/z (Th) | Lower bound retained in the modelled analysis. |
| Maximum m/z (Th) | Upper bound retained. The demo default is 500 Th, while this file extends to about 518.908 Th. Enabling the defaults will therefore remove the upper part of the file from the modelled display. |
| Additional response kernel m/Δm (FWHM) | Represents additional Gaussian broadening where the implementation's mass-spacing condition is met. It cannot sharpen the acquisition or recover lost resolution. **For this example file, its nonuniform mass spacing does not meet that condition, so v0.3.9 skips this broadening step. Changing this field alone should not broaden its spectrum.** |

### Detector & acquisition

| Field | Meaning and expected effect |
|---|---|
| Integration time (s; reference = 1 s) | Scales intensity relative to one second. It does not re-acquire data or choose a longer time interval from the file. |
| Detector gain multiplier | Uniformly multiplies signal before subsequent clipping and added effects. |
| Added background (a.u.) | Adds a constant baseline. |
| Added noise standard deviation (a.u.) | Adds simulated noise. The implementation uses a fixed random seed, so repeated identical calculations are reproducible rather than independent noisy acquisitions. |
| Saturation ceiling (a.u.) | Clips calculated values above the ceiling. A low setting can produce flat-topped peaks. This models clipping; it does not diagnose the original detector's saturation threshold. |

### Calibration & instrument state

| Field | Meaning and expected effect |
|---|---|
| Mass calibration drift (ppm) | Shifts the mass axis by the entered fractional offset. Positive values shift peaks to higher m/z; negative values shift them lower. At m/z 100, +10 ppm corresponds to approximately +0.001 Th. This is an imposed shift, not an automatic recalibration against reference ions. |


### Apply configuration & analyze — what happens

In **imported measurement mode**, Apply, Reset and configuration editing are disabled. Use Spectrum Workspace to change display range, source, aggregation and scale; those do not rewrite acquisition settings.

In a **new simulation**:

1. Enter the desired targets, reagent and environment and generate a synthetic HDF5 spectrum.
2. Set your illustrative configuration. Changing a reagent requires generating again; Apply alone does not alter the existing ion chemistry.
3. Leave the response checkbox off to analyze the stored synthetic spectrum, or check it to apply the illustrative response.
4. Click **Apply configuration & analyze**. The form is validated, the current From/To window is cleared and the spectrum is recalculated from the selected stored source.
5. Return to Spectrum Workspace. Inspect the model-status message, spectrum, statistics and peak table. The button itself does not switch panels.
6. Change one parameter at a time. For example, increasing dilution from 1 to 2 approximately halves the signal when additive background and clipping are absent.
7. Uncheck the response model and Apply to remove the extra transformation, or use Reset demo defaults.

Repeated Apply clicks recompute from the stored source; they do not repeatedly compound the last transformed output. New file ingestion disables the model. On the Vocus example, a demo maximum of 500 Th excludes data above 500 Th; use an appropriate range in your simulation comparisons.

| Action | Result |
|---|---|
| Changes pending | Form edits have not been applied. |
| Reset demo defaults | Restores default numeric values, I− and Ready; switches the model off and refreshes the synthetic spectrum. It does not recover original experimental settings. |
| Download configuration JSON | Exports the current simulation form and checkbox state, including unapplied edits. It does not export HDF5 data or certify an acquisition configuration. |

### Illustrative response equations

These formulas describe the code's transformation, not a validated physical instrument model. Let x be m/z and y the selected stored signal.

- Shifted mass: x′ = x × (1 + drift_ppm/10⁶).
- Transport delay: d = 60 × volume_mL / flow_mL_min seconds.
- Response fraction: f = 1 − exp(−max(0, elapsed_s − d)/response_s).
- Uniform multiplier: A = (1−loss/100) / dilution × f × reagent_signal × response_factor × transmission/100 × integration_s × gain.
- Before additional broadening: y₁ = max(y,0) × A × exp(−mass_rolloff × max(x′,0)/100).
- Optional Gaussian kernel: σ_bins = median(x′)/(R_kernel × 2.35482 × median bin spacing). It is applied only when the mass spacing is sufficiently uniform and the width exceeds the code's minimum. This adds broadening; it does not restore resolution. The first Vocus file's spacing fails this uniformity condition.
- Then add background + carryover + Gaussian noise of the requested standard deviation; a fixed random seed makes repeated identical computations reproducible.
- Clip to [0, saturation ceiling]. Standby/Fault replaces the result with zeros.
- Keep only minimum_mz ≤ x′ ≤ maximum_mz.

The displayed multiplier A does not include the additive background, noise, clipping or mass-dependent attenuation. Changing context-only temperatures, pressures, reaction time, E/N, humidity or vacuum produces no spectral change.

### LOD & LOQ Detection Capability

This is a separate **analysis study**, not editable acquisition metadata. It stays available for imported measurements, but the user must supply an applicable calibration. Its analyte or matrix describes the study and does not overwrite the file's recorded targets or environment.

| Input/action | Purpose and accepted content |
|---|---|
| Analyte | Known compound/element for the method; a name you supply, not an identification made by the app. |
| Formula | Optional target formula. |
| Quantifier ion m/z | Positive mass-to-charge value for the ion used in that method, including the correct adduct/fragment when relevant. |
| m/z tolerance | Positive matching interval in Th. Matching mass alone cannot distinguish interfering ions. |
| Concentration unit | Unit of calibration and reported limits, such as ppb or ng/L. |
| Matrix | Sample environment for the calibration study, such as air. It must match the use case and is distinct from the locked acquisition matrix. |
| Calculation method | Calibration curve; signal-to-noise estimate; or user-supplied limits. Both calculated methods require a calibration in this implementation. |
| Validation label | Describes supporting evidence. Selecting a label does not perform validation. Calculated results remain estimates. |
| Calibration points | At least three concentration,response pairs, one per line, with at least two distinct concentrations and a positive fitted slope. Use the same response definition and units as the analyzed peak intensity. |
| Blank responses | Replicate blank intensities, one per line. Two or more allow a sample standard deviation. If usable nonzero blank variation is absent, the app uses calibration residual variation. |
| User-supplied LOD / LOQ | Positive limits with LOQ ≥ LOD, visible for the user-supplied method. Limits alone do not provide a concentration conversion. |
| Calculate and apply LOD/LOQ | Fits or records the study and updates matching peak assessments. It is separate from Apply configuration & analyze. |
| Clear study | Removes the applied study and its results. |
| Download study JSON | Exports the recorded study/results for documentation. |

### Detection-capability formulas used by the app

For n calibration pairs (C[j], I[j]), a linear least-squares fit gives Î = a + S×C. The app requires S > 0.

| Result | Formula |
|---|---|
| Slope | S = Σ((C−mean C)(I−mean I)) / Σ((C−mean C)²). |
| Intercept | a = mean I − S×mean C. |
| R² | 1 − Σ(I−Î)² / Σ(I−mean I)²; unavailable if the denominator is zero. |
| Blank mean | Σ blank intensities / blank count. |
| Blank σ | sqrt(Σ(blank−mean blank)²/(blank count−1)). Used if there are at least two blanks and σ > 0. |
| Residual σ fallback | sqrt(Σ(I−Î)² / max(1,n−2)). Used when nonzero blank σ is unavailable. |
| Calibration-method LOD | 3.3×σ/S. |
| Calibration-method LOQ | 10×σ/S. |
| Corresponding response thresholds | I_LOD = a + S×LOD; I_LOQ = a + S×LOQ. |
| S/N-method response thresholds | I_LOD = mean blank + 3σ; I_LOQ = mean blank + 10σ. |
| S/N-method concentration limits | LOD = max(0,(I_LOD−a)/S); LOQ = max(0,(I_LOQ−a)/S). |
| Peak concentration | max(0,(peak intensity−a)/S). |
| Peak S/N | max(0,(peak intensity−mean blank)/σ). |

The fit uses peak-height responses here, not integrated chromatographic areas. Calibration, blank responses and measurement must share compatible aggregation, units and processing. Independently verify performance near the estimated limits before using them for decisions.

| Peak status | Rule |
|---|---|
| Not evaluated | Peak centroid falls outside the study's m/z tolerance. |
| Requires concentration result | No usable concentration conversion, as with user-supplied limits alone. |
| Below LOD | C < LOD. |
| Detected—not quantifiable | LOD ≤ C < LOQ. |
| Above calibration range | C ≥ LOQ and C exceeds the highest entered calibration concentration. |
| Quantifiable | C ≥ LOQ and not above the entered calibration maximum. This is the software rule, not an independent validation finding. |

## 3. TOFWERK HDF5

### Contents

- Instrument and suitability groups
- File selection and direct opening
- Evidence, checks and limitations
- Filters, refresh and export

| Item | Meaning and use |
|---|---|
| Review total | 97 files reviewed: 77 Good for dev, 18 Conditional, 2 No good as supplied. This is a saved assessment, not a live sensor or directory scan. |
| Vocus CI-TOF | 77 files: 71 good for development, 6 conditional. Includes split derivatives. |
| mipTOF | 15 files: 6 good, 8 conditional, 1 empty file. |
| Other / unconfirmed | 5 files: 4 conditional and 1 HDF5 read failure. Instrument domain is not forced into either of the other groups. |
| Good for dev | Accepted for the checked ingestion, display and replay use cases; not a blanket endorsement for chemical identification or supervised training. |
| Conditional | Follow the listed correction or verification steps, such as removing padded tails, aligning arrays or confirming instrument domain. |
| No good as supplied | Empty acquisition or a reproducible HDF5 structural read failure. A fresh/repaired copy or measured acquisition is needed. |
| Not training-ready | Labels, exposure windows, controls, calibration or independent run partitions need curation. This does not mean the spectra have no exploratory value. |
| File name, path, size, stored spectra | Identifies the reviewed object. Stored counts may include padded/unfinished buffers; read its reason/actions before treating them as measured observations. |
| Open in viewer | Opens the local file read-only and switches to Spectrum Workspace. Family is synchronized; acquisition inputs are locked. Connect the ADA drive if the file is missing. The app does not silently fetch it from the cloud. |
| Evidence & next steps | Shows reasons, required actions, provenance, instrument-classification basis and core checks. |
| SHA-256 | Content fingerprint of the inspected copy, useful for provenance comparison. Opening a file does not re-run the full review or verify its current content against that fingerprint. |
| Acquisition log | Recorded messages where available. A stop/abort needs valid-buffer interpretation, not an assumption that the whole run is useless. |
| Find a file or finding | Searches names, paths and reasons. |
| Instrument / ADA development filters | Narrows displayed rows by group and decision. |
| Refresh | Reloads the saved assessment JSON; it does not rescan or reassess source files. |
| Export table | Downloads the complete saved assessment as CSV, including rows currently hidden by filters. |

### Important findings to retain

- There are 27 split derivatives. Keep each derivative and its parent acquisition in the same ML train/validation/test partition.
- The empty mipTOF blank contains no measured spectra; it can be a schema fixture, not a measured negative example.
- The GC×GC copy failed an HDF5 structure read. The review does not prove whether the root cause is the delivered copy or a format/library compatibility issue.
- Twelve files have trailing zero-time buffers, whose raw buffers are zero or absent. Exclude the padded/unfinished portions rather than rejecting valid preceding observations automatically.
- Vocus experiment documentation notes noise/threshold issues and uncertain fentanyl extraction concentration. mipTOF notes describe contamination, solution changes, drift and an inlet interruption. The file-specific reasons retain these limitations.
- “Not recorded” means the app did not find an unambiguous supported metadata field. It does not prove that the operator never recorded the information elsewhere.

The review inventories objects and fully scans core numeric spectra, peak and timing arrays where readable. It does not exhaustively validate every auxiliary waveform, establish chemical identity, or certify a detection method. See Parameters and the experiment companions when making scientific acceptance decisions.

### Guide and source notes

The calculations above document this application's v0.3.9 implementation. The instrument walkthrough uses the official TOFWERK product descriptions and JEOL physics explanation linked in section 2. The diagram is an original explanatory drawing, not a vendor hardware drawing. All guide text and animation assets run locally; external reference links require internet access.
