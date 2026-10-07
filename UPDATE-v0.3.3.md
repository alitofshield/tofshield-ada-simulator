# Fourier and Fast Fourier Transform — v0.3.3

## Added

- Direct discrete Fourier transform (DFT), limited to 1,024 uniformly resampled points for responsive educational use.
- Radix-2 fast Fourier transform (FFT), using up to 8,192 uniformly resampled points.
- Optional mean/DC removal and Hann windowing.
- Linear and logarithmic amplitude display.
- Frequency-domain PNG export through the existing offline Plotly bundle.
- Summary of sampling interval, dominant non-DC spatial frequency, equivalent m/z spacing and calculation time.
- Peak Inspector estimates calculated from the full selected-window data before display reduction: baseline-corrected FWHM with interpolated half-height crossings, centroid m/z, resolving power `m/FWHM`, and a quality classification.

Peak-width results are marked **Estimated**, **Undersampled**, **Overlapping**, **Truncated**, **Unavailable**, or **No mass axis** as appropriate. They are analytical estimates, not official instrument specifications.

## Scientific boundary

The displayed transform is calculated from **signal intensity versus m/z** after interpolation onto an evenly spaced mass grid. Its frequency axis is therefore a spatial-frequency-like axis expressed as cycles per Thomson (cycles/Th), or cycles per sample when no mass axis exists. It may help reveal repeated peak spacing or processing artifacts.

It is not a transform of the instrument's raw detector waveform or flight-time transient and must not be interpreted as physical detector frequency. A true TOF frequency-domain analysis requires access to raw, uniformly sampled time-domain acquisition data before conversion to m/z.
