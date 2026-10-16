"""External research data. None is authorized as a tank calibration profile."""

CATALOG = [
    {
        "id": "taco",
        "name": "TACO litter images",
        "purpose": "Detector development",
        "url": "https://github.com/pedropro/TACO",
        "account_required": False,
        "license_note": "Toolkit MIT; retain COCO license records and verify each photo's license/attribution before reuse.",
        "limitations": "Outdoor waste images differ from overhead floating tank tokens; train/evaluate on your own tank footage too.",
    },
    {
        "id": "noaa-gdp",
        "name": "NOAA Global Drifter Program, six-hour QC",
        "purpose": "Geographic trajectory exploration",
        "account_required": False,
        "url": "https://www.aoml.noaa.gov/phod/gdp/interpolated/data/all.php",
        "license_note": "ERDDAP metadata supplies CC BY 4.0 and required NOAA acknowledgement; retain subset/access date.",
        "limitations": "Interpolated buoy positions, not plastic trajectories or pollution labels; drogue/depth behavior differs from floating tokens.",
    },
    {
        "id": "copernicus",
        "name": "Copernicus Marine ocean currents",
        "purpose": "Field-data exploration",
        "account_required": True,
        "url": "https://marine.copernicus.eu/",
        "license_note": "Use the product's current Copernicus Marine licence and acknowledgement; retain dataset/version/subset.",
        "limitations": "Ocean-grid surface current estimates cannot calibrate a tabletop tank or prove local debris origin.",
    },
]


def get_catalog(dataset_id):
    return next(row for row in CATALOG if row["id"] == dataset_id)
