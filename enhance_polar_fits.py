import argparse
from pathlib import Path

import numpy as np
from astropy.io import fits
from scipy.ndimage import gaussian_filter, gaussian_filter1d

try:
    from skimage import exposure
except ModuleNotFoundError:
    exposure = None


def robust_normalize(image, low_pct=1.0, high_pct=99.5):
    low = np.percentile(image, low_pct)
    high = np.percentile(image, high_pct)
    if high <= low:
        return np.zeros_like(image, dtype=np.float32)
    scaled = (image - low) / (high - low)
    return np.clip(scaled, 0.0, 1.0).astype(np.float32)


def enhance_polar_image(
    image,
    smooth_theta=1.0,
    smooth_r=0.8,
    background_theta=8.0,
    background_r=25.0,
    ridge_sigma=1.2,
):
    """
    Enhance weak ring ridges in an already-polar image.

    Axes are assumed to be:
    - axis 0: theta
    - axis 1: radius
    """
    arr = np.asarray(image, dtype=np.float32)

    # Mild denoising while keeping thin ridges.
    smoothed = gaussian_filter(arr, sigma=(smooth_theta, smooth_r), mode="nearest")

    # Remove broad background so weak rings stand out more clearly.
    background = gaussian_filter(
        smoothed, sigma=(background_theta, background_r), mode="nearest"
    )
    highpass = smoothed - background

    # Highlight narrow radial ridges using the negative second derivative in r.
    ridge_base = gaussian_filter1d(highpass, sigma=ridge_sigma, axis=1, mode="nearest")
    d2r = gaussian_filter1d(
        ridge_base, sigma=ridge_sigma, axis=1, order=2, mode="nearest"
    )
    ridge = -d2r

    # Keep only positive ridge-like response.
    ridge = np.clip(ridge, 0.0, None)

    # Blend the ridge response with the background-subtracted image so the
    # resulting file is still visually interpretable in the FITS viewer.
    highpass_pos = np.clip(highpass, 0.0, None)
    ridge_n = robust_normalize(ridge)
    highpass_n = robust_normalize(highpass_pos)
    enhanced = 0.75 * ridge_n + 0.25 * highpass_n

    return enhanced.astype(np.float32)


def enhance_unsharp(image, smooth_theta=1.0, smooth_r=1.0, blur_theta=6.0, blur_r=18.0):
    arr = np.asarray(image, dtype=np.float32)
    base = gaussian_filter(arr, sigma=(smooth_theta, smooth_r), mode="nearest")
    blurred = gaussian_filter(base, sigma=(blur_theta, blur_r), mode="nearest")
    detail = base - blurred
    enhanced = np.clip(0.35 * robust_normalize(base) + 0.65 * robust_normalize(detail), 0.0, 1.0)
    return enhanced.astype(np.float32)


def enhance_clahe(image, smooth_theta=1.0, smooth_r=1.0, clip_limit=0.02, kernel_theta=24, kernel_r=96):
    if exposure is None:
        raise RuntimeError("scikit-image is required for CLAHE mode but is not installed")

    arr = np.asarray(image, dtype=np.float32)
    base = gaussian_filter(arr, sigma=(smooth_theta, smooth_r), mode="nearest")
    norm = robust_normalize(base)
    enhanced = exposure.equalize_adapthist(
        norm,
        kernel_size=(kernel_theta, kernel_r),
        clip_limit=clip_limit,
    )
    return np.asarray(enhanced, dtype=np.float32)


#def enhance_bandpass(image, smooth_theta=1.0, smooth_r=0.8, low_r=3.0, high_r=24.0):
def enhance_bandpass(image, smooth_theta=1.0, smooth_r=0.8, low_r=2.0, high_r=20.0):
    arr = np.asarray(image, dtype=np.float32)
    base = gaussian_filter(arr, sigma=(smooth_theta, smooth_r), mode="nearest")
    lowpass_small = gaussian_filter1d(base, sigma=low_r, axis=1, mode="nearest")
    lowpass_large = gaussian_filter1d(base, sigma=high_r, axis=1, mode="nearest")
    band = lowpass_small - lowpass_large
    band = np.clip(band, 0.0, None)
    return robust_normalize(band).astype(np.float32)


def load_fits_image(path):
    with fits.open(path) as hdul:
        data = np.array(hdul[0].data, dtype=np.float32, copy=True)
        header = hdul[0].header.copy()
    if data.ndim != 2:
        raise ValueError(f"Expected a 2D FITS image, got shape {data.shape}")
    return data, header


def save_fits_image(path, image, header, source_name):
    out_header = header.copy()
    out_header["HISTORY"] = f"Enhanced from {source_name}"
    out_header["HISTORY"] = "Mild smoothing, background subtraction, radial ridge enhancement"
    fits.PrimaryHDU(data=np.asarray(image, dtype=np.float32), header=out_header).writeto(
        path, overwrite=True
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Enhance weak ridges in a polar-coordinate FITS image."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("polardate.FTS"),
        help="Input polar FITS image.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output enhanced FITS image for single-mode runs.",
    )
    parser.add_argument(
        "--mode",
        choices=("all", "ridge", "unsharp", "clahe", "bandpass"),
        default="all",
        help="Enhancement mode. Default writes all available modes.",
    )
    parser.add_argument("--smooth-theta", type=float, default=1.0)
    parser.add_argument("--smooth-r", type=float, default=0.8)
    parser.add_argument("--background-theta", type=float, default=8.0)
    parser.add_argument("--background-r", type=float, default=25.0)
    parser.add_argument("--ridge-sigma", type=float, default=1.2)
    parser.add_argument("--blur-theta", type=float, default=6.0)
    parser.add_argument("--blur-r", type=float, default=18.0)
    parser.add_argument("--clip-limit", type=float, default=0.02)
    parser.add_argument("--kernel-theta", type=int, default=24)
    parser.add_argument("--kernel-r", type=int, default=96)
    parser.add_argument("--low-r", type=float, default=3.0)
    parser.add_argument("--high-r", type=float, default=24.0)
    return parser.parse_args()


def main():
    args = parse_args()
    image, header = load_fits_image(args.input)
    input_stem = args.input.stem

    mode_to_func = {
        "ridge": lambda: enhance_polar_image(
            image,
            smooth_theta=args.smooth_theta,
            smooth_r=args.smooth_r,
            background_theta=args.background_theta,
            background_r=args.background_r,
            ridge_sigma=args.ridge_sigma,
        ),
        "unsharp": lambda: enhance_unsharp(
            image,
            smooth_theta=args.smooth_theta,
            smooth_r=args.smooth_r,
            blur_theta=args.blur_theta,
            blur_r=args.blur_r,
        ),
        "clahe": lambda: enhance_clahe(
            image,
            smooth_theta=args.smooth_theta,
            smooth_r=args.smooth_r,
            clip_limit=args.clip_limit,
            kernel_theta=args.kernel_theta,
            kernel_r=args.kernel_r,
        ),
        "bandpass": lambda: enhance_bandpass(
            image,
            smooth_theta=args.smooth_theta,
            smooth_r=args.smooth_r,
            low_r=args.low_r,
            high_r=args.high_r,
        ),
    }

    modes = list(mode_to_func.keys()) if args.mode == "all" else [args.mode]

    for mode in modes:
        try:
            enhanced = mode_to_func[mode]()
        except RuntimeError as exc:
            print(f"Skipped {mode}: {exc}")
            continue

        if args.mode == "all":
            output_path = args.input.with_name(f"{input_stem}_{mode}.FTS")
        else:
            output_path = args.output or args.input.with_name(f"{input_stem}_{mode}.FTS")

        save_fits_image(output_path, enhanced, header, args.input.name)
        print(f"Saved {mode} enhanced FITS image to {output_path}")


if __name__ == "__main__":
    main()
