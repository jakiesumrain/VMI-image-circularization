# VMI Image Circularization

Correct radial distortions in Velocity Map Imaging (VMI) images using a Fourier-series distortion model extracted from ring-fitting software.

## Overview

Velocity Map Imaging (VMI) is a technique in physical chemistry and molecular physics that measures the velocity distribution of charged particles (electrons, ions) produced in photodissociation or photoionization experiments. The raw 2D projection image contains concentric rings whose radii encode particle kinetic energies.

Real-world instruments introduce optical and electrostatic distortions that make these rings deviate from perfect circles. This repository provides tools to:

- **Model** the distortion as an angle-dependent radial displacement around a fixed center
- **Correct** the image via inverse warping to produce a circularized output
- **Enhance** weak ring features in polar FITS images so they can be reliably fitted by ring-detection software

The project works in tandem with the **FITS Viewer and VMI Analysis** Windows program (available on the [Releases page](https://github.com/user/VMI-image-circularization/releases)), which is used for manual ring annotation and coefficient extraction.

> **FITS Viewer and VMI Analysis** is developed by Jason Gascooke and Warren Lawrance (Flinders University) and distributed under the [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) license.  
> DOI: [10.4226/86/59278ab872838](https://doi.org/10.4226/86/59278ab872838)  
> Source: [Flinders University Research Repository](https://open.flinders.edu.au/articles/dataset/FITS_Viewer_and_VMI_Analysis_A_Program_for_Analysing_and_Circularising_VMI_Images_version_4_0_/16881961)

## Repository Contents

| File | Purpose |
|------|---------|
| `circularization.py` | Main circularization script (~930 lines). Reads distortion coefficients from the FITS software and remaps the Cartesian image. |
| `enhance_polar_fits.py` | Preprocessing script (~217 lines). Enhances faint rings in polar FITS images so the FITS Viewer can detect them. |
| `circularization_manual.md` | Detailed user manual covering assumptions, parameters, workflows, and troubleshooting. |
| `README.md` | This file. |

> **FITS Viewer and VMI Analysis** (`FITS/`) is not included in the repository itself. Download it from the [Releases page](https://github.com/user/VMI-image-circularization/releases) or directly from [Flinders University](https://open.flinders.edu.au/articles/dataset/FITS_Viewer_and_VMI_Analysis_A_Program_for_Analysing_and_Circularising_VMI_Images_version_4_0_/16881961).

## How It Works

The circularization approach used here is inspired by the method described in **Gascooke, Gibson, and Lawrance (2017)** [\[1\]](#references), with a key simplification: the image center is **fixed by the user** via the `--center` flag based on physical judgment, rather than being determined as part of the optimisation. This is appropriate when the center is already well-known from the experimental setup.

### Distortion Model

The script assumes the image distortion is a **radial displacement about a fixed center** — that is, every pixel is shifted inward or outward along its radial line, but not tangentially.

For each angle θ, the distorted source radius is modeled as:

```
r_old = r_circ + Δr(r_circ, θ)
```

The displacement Δr is expanded as a Fourier series in angle, with radius-dependent coefficients:

```
Δr(r, θ) = Σₙ [Aₙ(r) sin(nθ) + Bₙ(r) cos(nθ)]
```

where:
- **r_circ** is the circularized (ideal) radius
- **r_old** is the actual distorted radius in the raw image
- **Aₙ(r)** and **Bₙ(r)** are extracted from the FITS software at discrete radii and then fitted with either:
  - **PCHIP interpolation** (recommended): passes exactly through all measured points with shape-preserving splines
  - **Polynomial fit**: a global polynomial constrained to vanish at r = 0

### Inverse Warping

The script uses **inverse warping** (also called backward mapping):

1. For every pixel in the output (circularized) image, compute its polar coordinates (r_circ, θ)
2. Use the distortion model to find the corresponding source location (r_old, θ) in the raw image
3. Interpolate the raw image at that location using `scipy.ndimage.map_coordinates`

This guarantees every output pixel receives a value — no holes or gaps, unlike forward mapping.

### Optional Radial Reassignment

An additional mapping layer (via `--reassign-file`) allows you to shift the circularized rings to user-specified radii. This is useful for calibration against known photoelectron kinetic energies. The mapping is:

```
r_fixed → r_circ → r_old
```

where `r_fixed` is the output pixel radius, `r_circ` comes from the reassignment interpolator, and `r_old` comes from the distortion model. Outside the specified range, the mapping falls back to identity (no reassignment).

### Jacobian Correction

By default, the script applies a Jacobian intensity correction that preserves local count density under the radial remapping. In practice the Jacobian depends on derivatives of the fitted model, which are often less reliable than the ring positions themselves. **It is recommended to disable it with `--no-jacobian`** unless you have validated that it improves your intensity calibration.

## Workflow

### Typical Pipeline

```
Raw experimental image
        ↓
Convert to text format (image.txt)
        ↓
Convert to polar coordinates → view in FITS Viewer
        ↓
FITS Viewer: annotate ring centers, fit trig coefficients, export extracted.txt
        ↓
circularization.py --input image.txt --extracted extracted.txt ...
        ↓
Circularized Cartesian image (image_circularized.txt)
```

### When Rings Are Too Faint

If the FITS Viewer struggles to detect rings in the polar image:

1. Run `enhance_polar_fits.py` on the polar FITS file
2. Open the enhanced output in the FITS Viewer
3. Fit rings on the enhanced image
4. Export the coefficients and use them with `circularization.py` on the *original* Cartesian image

## Installation

### Requirements

- **Python 3.9+**
- **NumPy**
- **SciPy**
- **Matplotlib** (optional, for diagnostic plots)
- **Astropy** (for `enhance_polar_fits.py`, FITS I/O)
- **scikit-image** (optional, for CLAHE enhancement mode)

### Setup (using uv)

```powershell
uv pip install numpy scipy matplotlib astropy scikit-image
```

Or with pip:

```powershell
pip install numpy scipy matplotlib astropy scikit-image
```

## Usage

### Basic Circularization

```powershell
uv run circularization.py `
  --input image.txt `
  --output image_circularized.txt `
  --center 511 511 `
  --shape 1023 1023 `
  --extracted extracted.txt `
  --max-trig-n 6 `
  --polar-dr 0.5 `
  --radial-model interp `
  --no-jacobian
```

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--center XC YC` | `511 511` | Image center in Python (row, column) indexing |
| `--shape NY NX` | `1023 1023` | Image dimensions |
| `--extracted PATH` | `extracted.txt` | Trig-fit export file from FITS Viewer |
| `--max-trig-n N` | *inferred* | Highest Fourier order to include |
| `--polar-dr VALUE` | `1.0` | Radial step size used when creating the polar image. **Critical** — if the polar image used `dr = 0.5`, set this to `0.5`. All extracted radii and coefficients are interpreted in these units. |
| `--radial-model {interp,poly}` | `interp` | Radial model for Aₙ(r), Bₙ(r). `interp` (PCHIP) is recommended. |
| `--poly-order N` | `2` | Polynomial order (only used with `--radial-model poly`) |
| `--no-jacobian` | *(off)* | Disable the Jacobian intensity correction |
| `--reassign-file PATH` | *none* | Two-column file (r_circ, r_fixed) for radius recalibration |
| `--summary-only` | *(off)* | Parse and print extracted coefficients without remapping |
| `--no-plots` | *(off)* | Skip diagnostic plots |
| `--plot-dir PATH` | `trig_fit_plots/` | Directory for diagnostic plots |

### Polar Image Enhancement

```powershell
uv run enhance_polar_fits.py `
  --input polardate.FTS `
  --mode all
```

Available enhancement modes: `ridge`, `unsharp`, `clahe`, `bandpass`, `all`. Each mode is saved as a separate `.FTS` file with the mode name appended.

> **Note:** In practice, the `bandpass` mode has proven the most effective enhancement for ring detection. It applies a radial bandpass filter that isolates features at typical ring widths, making faint rings clearly visible to the FITS Viewer's fitting algorithm.

### Inspecting Extracted Data Only

```powershell
uv run circularization.py `
  --summary-only `
  --extracted extracted.txt `
  --max-trig-n 6 `
  --polar-dr 0.5
```

This prints all extracted ring radii and Fourier coefficients without running the full circularization.

## Input Files

### image.txt (Cartesian image)

A whitespace-separated text file of pixel intensities, typically 1023×1023. Must match `--shape`.

### extracted.txt (Fourier coefficients)

Exported from the FITS Viewer / VMI Analysis software. Contains one block per fitted ring with:

- `Gaussian Centre` — the ring radius in polar-image radial units
- `Trig Term sin(n*theta)` — Aₙ coefficient at that radius
- `Trig Term cos(n*theta)` — Bₙ coefficient at that radius

Each block also includes 1σ uncertainties used for weighted fitting.

### reassign.txt (optional)

A two-column text file (comments with `#` allowed):

```
# r_circ  r_fixed
0         0
17.62     20
43.18     45
...
```

Both columns are in polar-image radial units. The `(0, 0)` point is added automatically if missing.

## Output Files

### Cartesian output

- **`image_circularized.txt`** (or custom `--output` path) — the corrected image as a whitespace-separated text file

### Diagnostic plots

Written to `trig_fit_plots/` (configurable via `--plot-dir`):

| File | Description |
|------|-------------|
| `trig_order_1.png` | A₁(r) and B₁(r) data with fitted/interpolated model |
| `trig_order_2.png` | A₂(r) and B₂(r) data with fitted/interpolated model |
| ... | Higher orders as available |
| `reassignment_map.png` | The r_fixed → r_circ mapping (only if `--reassign-file` is used) |

## Coordinate Conventions

### Angle

- θ is measured **anticlockwise from +x**
- The geometry uses **FITS-style y-up** coordinates
- **Do not flip the image array manually** — the script handles this internally

### Center

- Center coordinates use **Python indexing**: `--center xc yc`
- The typical center for a 1023×1023 image is `511 511`

### Radius Units

- All extracted radii (Gaussian Centre, Aₙ, Bₙ) and reassignment points are in **polar-image radial units**, not Cartesian pixels
- If the polar image was generated with `Radial Step Size = 0.5`, use `--polar-dr 0.5`
- The script handles the conversion internally — do not manually rescale the coefficients

## Recommendations

1. **Use `--radial-model interp`** — PCHIP interpolation passes through all extracted points and respects the origin constraint
2. **Limit `--max-trig-n`** to orders that are physically meaningful; higher orders often fit noise
3. **Use `--no-jacobian`** unless you have validated the Jacobian correction for your instrument
4. **Get `--polar-dr` right** — this is the most common source of scaling errors
5. **Strong inner rings** are more reliable constraints than weak incomplete outer arcs
6. **Use `--summary-only` first** to inspect your extracted data before running the full correction

## Advanced: Radial Reassignment

The radial reassignment feature lets you anchor specific rings to known radius values. This is useful when:

- You have a calibration spectrum with known peak positions
- You need to correct systematic radial offsets in the instrument
- You want to match ring positions across different experimental conditions

The reassignment map uses PCHIP interpolation and defaults to identity outside the supplied radius range (to avoid stripe artifacts).

## Dependencies

| Package | Required for | Notes |
|---------|-------------|-------|
| `numpy` | Everything | Core array operations |
| `scipy` | Interpolation, fitting, image filters | PCHIP, curve_fit, map_coordinates, gaussian_filter |
| `matplotlib` | Diagnostic plots | Optional — scripts run without it |
| `astropy` | FITS I/O | Required only for `enhance_polar_fits.py` |
| `scikit-image` | CLAHE enhancement | Optional — for `--mode clahe` only |

## References

1. Gascooke, J. R., Gibson, S. T., & Lawrance, W. D. (2017). A "circularisation" method to repair deformations and determine the centre of velocity map images. *The Journal of Chemical Physics*, *147*(1), 013924. [https://doi.org/10.1063/1.4981024](https://doi.org/10.1063/1.4981024)

## License

### Python Scripts

The Python scripts (`circularization.py`, `enhance_polar_fits.py`) in this repository are provided for research use. If no explicit license file is present, they are distributed under the terms of the [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) license.

### FITS Viewer and VMI Analysis

The `FITS Viewer and VMI Analysis` program by **Jason Gascooke and Warren Lawrance (Flinders University)** is distributed under the [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) license. It is available for download on the [Releases page](https://github.com/user/VMI-image-circularization/releases) or directly from Flinders University.

**Attribution:**

> Gascooke, Jason; Lawrance, Warren (2017): FITS Viewer and VMI Analysis: A Program for Analysing and Circularising VMI Images (version 4.0). Flinders University. Dataset.  
> DOI: [10.4226/86/59278ab872838](https://doi.org/10.4226/86/59278ab872838)  
> Available at: https://open.flinders.edu.au/articles/dataset/FITS_Viewer_and_VMI_Analysis_A_Program_for_Analysing_and_Circularising_VMI_Images_version_4_0_/16881961
