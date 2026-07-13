# `circularization.py` User Manual

## Purpose

`circularization.py` circularizes a distorted VMI image by:

- reading ring-fit parameters exported from the FITS Viewer / VMI Analysis software
- building a radius-dependent distortion model
- optionally reassigning circularized ring radii to user-chosen values
- remapping the original Cartesian image onto a corrected image

The script is designed for the workflow used in this folder:

- the distortion model is extracted from a polar image in the FITS software
- the original image is stored as `image.txt`
- the fitted coefficients are stored in `extracted.txt` or another exported text file

This manual explains the assumptions, input units, options, and recommended workflow.

---

## Core Idea

The script assumes that the image distortion is mainly a **radial distortion about a fixed center**.

For each angle `theta`, the distorted source radius is modeled as:

`r_old = r_circ + Delta r(r_circ, theta)`

with

`Delta r(r, theta) = sum_n [A_n(r) sin(n theta) + B_n(r) cos(n theta)]`

where:

- `r_old` is the distorted radius in the original image
- `r_circ` is the circularized radius
- `A_n(r)` and `B_n(r)` are extracted from the FITS software and then interpolated or fit as functions of radius

The script uses **inverse warping**:

- for each output pixel, compute where it came from in the distorted source image
- interpolate the source image at that location

This avoids holes in the output image.

---

## Important Coordinate Conventions

### Angle Convention

The script now uses the same effective geometry as the FITS software:

- `theta` increases **anticlockwise**
- the geometry is treated in **FITS-style `y`-up coordinates**

This was a critical correction. Do **not** flip the image array manually anymore.

### Center Convention

The center passed to the script is in Python indexing:

- `center = (xc, yc)`

For your workflow this is typically:

- `--center 511 511`

### Radius Units

This is the most important practical point.

The extracted values in `extracted.txt` are assumed to be in the **radial units of the polar image**, not automatically in Cartesian pixels.

If your polar image was created with:

- `Radial Step Size = 0.5`

then one polar radial unit corresponds to:

- `0.5` Cartesian pixels

Use:

- `--polar-dr 0.5`

in that case.

The script then interprets:

- `Gaussian Centre`
- `A_n`
- `B_n`
- `r_circ` values in `reassign.txt`
- `r_fixed` values in `reassign.txt`

all in **polar-image radial units**.

The script converts internally between:

- polar-model radial units
- Cartesian image-pixel radius

Do **not** manually rescale the extracted coefficients if you use `--polar-dr` correctly.

---

## Input Files

### 1. Original image

The original distorted Cartesian image is read from a whitespace-separated text file, usually:

- `image.txt`

It must match the shape given by `--shape`.

Example:

- `1023 x 1023`

### 2. Extracted fit parameters

The script reads the exported trig-fit results from a text file, usually:

- `extracted.txt`

or for an alternative extraction:

- `extracted-polar.txt`

Each block should contain:

- `Gaussian Centre`
- `Trig Term sin(n*theta)`
- `Trig Term cos(n*theta)`

The script parses these automatically.

### 3. Optional reassignment file

You may optionally supply a reassignment file:

- `reassign.txt`

This file must contain two columns:

- first column: `r_circ`
- second column: `r_fixed`

Both columns must be in **polar-image radial units**.

Example:

```txt
# r_circ  r_fixed
0         0
17.62     20
43.18     45
72.01     70
109.74    110
144.37    145
175.95    176
214.73    215
300.33    300
```

The script automatically adds `0 -> 0` if missing.

---

## Radial Models for `A_n(r)` and `B_n(r)`

The script supports two radial models.

### 1. `interp` (recommended)

Option:

- `--radial-model interp`

This builds a shape-preserving PCHIP interpolator through the extracted values.

Advantages:

- passes through all extracted points
- respects the origin constraint through `(0, 0)`
- usually better than a high-order global polynomial

This is the current default.

### 2. `poly`

Option:

- `--radial-model poly`

This fits a global polynomial with no constant term:

- `a_k r^k + ... + a_1 r`

Set the order with:

- `--poly-order N`

Advantages:

- smooth derivative
- Jacobian correction tends to be milder

Disadvantages:

- can underfit or overfit
- high orders can behave badly near the outer edge

---

## Reassignment Map

If `--reassign-file` is provided, the script applies two radial operations:

1. `r_fixed -> r_circ`
2. `r_circ -> r_old`

More explicitly:

- the output image is defined on `r_fixed`
- the reassignment map converts that to `r_circ`
- the circularization model converts that to `r_old`

So the total mapping is:

`r_fixed -> r_circ -> r_old`

This is implemented as two composed maps because it is:

- clearer physically
- easier to debug
- safer for Jacobian handling

### Outside the reassignment range

The reassignment map now behaves as:

- inside the supplied range: interpolation
- below the first point: identity
- above the last point: identity

This avoids artificial stripe artifacts outside the outermost reassigned feature.

### Reassignment plot

If you use `--reassign-file`, the script saves:

- `trig_fit_plots/reassignment_map.png`

This shows the inverse map:

- horizontal axis: `r_fixed`
- vertical axis: `r_circ`

in polar-image radial units.

---

## Jacobian Correction

By default, the script applies a Jacobian intensity correction.

This tries to preserve local count density under the radial remap.

You can disable it with:

- `--no-jacobian`

### Recommendation

Use `--no-jacobian` unless you have validated that the Jacobian correction improves, rather than distorts, your relative intensities.

Reason:

- the geometric correction depends mainly on `Delta r`
- the Jacobian depends on derivatives of the model
- those derivatives are often less reliable than the extracted ridge positions

So for many practical circularization tasks, geometry-only correction is safer.

---

## Command-Line Options

### Required / main options

- `--input`
  - path to the distorted Cartesian image text file

- `--output`
  - path to the corrected output text file

- `--center XC YC`
  - image center in Python indexing

- `--shape NY NX`
  - image shape

- `--extracted`
  - exported trig-fit file from the FITS software

- `--max-trig-n`
  - highest trig order to use

- `--polar-dr`
  - radial step size used in the polar image

### Radial model options

- `--radial-model interp|poly`
- `--poly-order N`

### Plotting options

- `--plot-dir`
  - directory for fit plots

- `--no-plots`
  - skip diagnostic plots

### Jacobian option

- `--no-jacobian`

### Reassignment option

- `--reassign-file`

### Summary mode

- `--summary-only`
  - parse and print extracted coefficients without remapping the image

---

## Typical Workflows

### Workflow A: circularize only

Example:

```powershell
uv run circularization.py `
  --input image.txt `
  --output image_circularized.txt `
  --center 511 511 `
  --shape 1023 1023 `
  --extracted .\extracted-polar.txt `
  --max-trig-n 6 `
  --polar-dr 0.5 `
  --radial-model interp `
  --no-jacobian
```

Use this when:

- you want geometric circularization only
- extracted radii and coefficients are in polar-image radial units

### Workflow B: circularize and reassign radii

Example:

```powershell
uv run circularization.py `
  --input image.txt `
  --output image_circularized_reassigned.txt `
  --center 511 511 `
  --shape 1023 1023 `
  --extracted .\extracted-polar.txt `
  --max-trig-n 6 `
  --polar-dr 0.5 `
  --radial-model interp `
  --reassign-file .\reassign.txt `
  --no-jacobian
```

Use this when:

- you want specific extracted rings to land at chosen radii

### Workflow C: inspect extracted data only

```powershell
uv run circularization.py `
  --summary-only `
  --extracted .\extracted-polar.txt `
  --max-trig-n 6 `
  --polar-dr 0.5
```

---

## Output Files

### Main output

- corrected Cartesian image as a text file

### Diagnostic plots

Saved in:

- `trig_fit_plots/`

May include:

- `trig_order_1.png`, `trig_order_2.png`, ...
- `reassignment_map.png`

---

## How to Interpret the Diagnostic Plots

### `trig_order_n.png`

Shows:

- extracted `A_n(r)` and `B_n(r)` points
- uncertainties
- interpolated or polynomial model curves

Use these to judge whether:

- the radial model is smooth and plausible
- higher-order terms are meaningful or mostly noise

### `reassignment_map.png`

Shows:

- how output radius `r_fixed` maps back to circularized radius `r_circ`

Use it to check that:

- the map is monotone
- the supplied reassignment points behave as expected

---

## Common Problems and Their Meaning

### 1. Circularization improves inner rings but not the outermost incomplete feature

Likely causes:

- the outer feature is not a full circular ring
- it is incomplete or split into separate segments
- a trig fit can pass through it visually, but it is not a reliable global ring constraint

### 2. Strange stripes outside the outermost reassigned ring

Cause:

- old versions of the reassignment code clipped to the last point

Fix:

- current code now uses identity outside the reassignment range

### 3. Results look wrong unless the image is flipped vertically

Cause:

- older geometry used the wrong effective angle sign

Fix:

- current code now uses FITS-style `y`-up geometry directly
- do **not** manually flip the image anymore

### 4. Reassigned radii look wrong by a factor of two

Cause:

- `--polar-dr` is wrong or missing

Example:

- if polar radial step was `0.5`, you must use:
  - `--polar-dr 0.5`

### 5. Jacobian changes peak contrast too much

Cause:

- Jacobian depends on model derivatives
- derivatives can be less reliable than ridge positions

Fix:

- use `--no-jacobian`

---

## Recommended Settings

For your present workflow, a good starting point is:

- `--radial-model interp`
- `--max-trig-n` set only as high as justified by the extracted data
- `--polar-dr 0.5` if the polar image was created with `dr = 0.5`
- `--no-jacobian`

Use reassignment only when you need explicit radius anchoring.

---

## Practical Notes

- The script assumes the center is already known and fixed.
- The extracted coefficients must come from the same center choice.
- The quality of the correction depends strongly on the quality of the extracted rings.
- Complete, strong inner rings are much more reliable constraints than weak incomplete outer arcs.

---

## Summary

`circularization.py` now supports:

- FITS-consistent angle geometry
- polar-image radial units through `--polar-dr`
- interpolation or polynomial radial models
- optional reassignment from `r_circ` to user-defined `r_fixed`
- optional Jacobian correction
- diagnostic plots for both trig fits and reassignment

The most important user responsibilities are:

- use the correct center
- use the correct `--polar-dr`
- supply reliable extracted rings
- avoid overinterpreting incomplete outer features as perfect circular constraints
