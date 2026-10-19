# cycle-navigator

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![engine: pheno-engine v0.1.0](https://img.shields.io/badge/engine-pheno--engine%20v0.1.0-orange)](https://github.com/osmarluiz/pheno-engine)
[![Licence: MIT](https://img.shields.io/badge/licence-MIT-green)](LICENSE)

A field-survey tool for cropping systems. You walk the landscape month by month on a PlanetScope
time series, click a field, see its year as a curve with the crop cycles already detected, and
record what the farmer tells you was planted in each part of that year — and whose land it is.

The phenometric engine is not in this repository. The cycle boundaries you see pre-drawn come from
[`pheno-engine`](https://github.com/osmarluiz/pheno-engine), pinned by tag in `pyproject.toml`, so
what a surveyor confirms or corrects in the field is a reply about the same reading the analyses use.

## What it does

**Navigate.** One date at a time, one way of seeing it: RGB natural, false colour (NIR), NDVI of the
month, or the year composites (NDVI-temporal, phenology, MNF, rainy/dry RGB, classification). The
arrow keys step through the months. Nothing is drawn over the map except what you put there.

**Record the year of a field.** Click a field: the bottom panel draws twelve months of NDVI (the
crop year), with the cycles the engine detected already shaded as bands. The farmer talks; you name
each band (free text with autocomplete), set a confidence per band, drag the edges — they snap to
whole months, because the data is monthly — and save. The point is stored with its curve. A context
strip shows the whole series (54 months) and lets you move or widen the window; detection always
runs per crop year, never across the whole strip, because the engine assumes twelve months from
October.

**Record whose land it is.** Draw the farm the way any GIS does (click vertices, double-click to
close, Esc to cancel), or start from a ready-made perimeter: the public **CAR** registry (SICAR) can
be loaded as a layer, inspected by clicking (code, municipality, declared vs measured area, fiscal
modules, status), and adopted as a farm with one click in edit mode. The registry has no owner names
or contacts — those still come from the conversation. Every point inside a farm inherits its owner
and contact, so the cadastre is typed once.

**Keep it findable.** Two attribute tables — farms, and labelled points — open on demand. Double-click
a row and the map centres on it and reopens its curve. Everything exports to GeoPackage, Shapefile
or CSV, one feature per band, so it colours by crop in QGIS without unpacking anything.

## Why it looks the way it does

- *Bands come pre-drawn from the engine, but the crop field opens empty.* Nobody draws two
  boundaries per field with a producer waiting; and a pre-filled "Soy" would be accepted without
  reading, producing soy fields nobody affirmed.
- *A label is a list of bands, per crop year.* A field that is soy in October and maize in March is
  neither; it is two crops in one pixel, and that succession is what the cycle count reads. The same
  field is soy one year and maize the next, so each crop year keeps its own file.
- *Confidence is per band.* The producer is sure about the main crop and hesitant about the second.
  Doubt is drawn fainter, and whoever trains on this later can keep only the *certo* bands.
- *Modes are explicit.* Identify, draw, edit — the same click means three things, so the active one
  is always lit, and Esc returns to identify.

## Install

```bash
pip install -e ".[dev,pivots]"
```

`pivots` pulls `geopandas`, needed for the CAR layer and for GeoPackage/Shapefile export. The tool
opens without it. On Windows, pin Qt — `PyQt6==6.7.1 PyQt6-Qt6==6.7.3 PyQt6-sip==13.8.0` — newer
pairs have failed to load `QtCore` on some machines.

## Data

The tool reads a monthly satellite time series over an area of interest, cropped to one grid:

```
<aoi>/cube/ride_{YYYYMM}_aoi.tif        4 bands (B,G,R,NIR) uint16, nodata 65535, scale 10000,
                                         tiled, with overviews — one file per month, all months you have
<aoi>/input/basemap_ndvitemporal_aoi.tif  3-band uint8 year composites (required: ndvitemporal,
<aoi>/input/basemap_pheno_aoi.tif         pheno, mnf; optional: rgb_chuvoso, rgb_seco)
<aoi>/input/basemap_mnf_aoi.tif
<aoi>/products/basemap_class_aoi.tif      uint8 class raster — defines the reference grid
<aoi>/car/car_aoi.gpkg                    optional: CAR property perimeters, clipped to the AOI
<aoi>/pontos/                             written by the tool: points per crop year, farms, surveyor
```

Overviews matter: without them every pan reads at full resolution and the tool stalls over a large
area. `gdaladdo -r average <file>.tif 2 4 8 16 32`. It ships no data; it was developed on a
PlanetScope series over the RIDE-DF (Brazilian Cerrado), ~20 000 km² at 4.8 m.

## Configure

Copy `cycle-navigator.example.toml` to `cycle-navigator.toml` next to the executable (or in the
working directory) and edit:

```toml
aoi   = "dados"                       # relative paths resolve next to this file
meses = [202009, 202010, ..., 202502] # every month you have; the tool groups crop years itself
```

Crop years are October to September; only complete ones are offered. Everything declared is checked
at start-up, so a wrong path fails with the offending name rather than thirty seconds into loading.

## Run

```bash
cycle-navigator                      # config found by the search order
cycle-navigator --config other.toml
```

## Executables

`build/cycle-navigator.spec` builds a one-folder application with PyInstaller:

```bash
pip install pyinstaller
cd build && pyinstaller --noconfirm cycle-navigator.spec     # -> build/dist/CycleNavigator/
```

Windows builds on Windows; macOS builds only on macOS. `.github/workflows/build.yml` builds all
three (Windows x64, macOS arm64, macOS x64) and publishes them as artifacts — run it from the Actions
tab. Put `cycle-navigator.toml` and the `dados/` folder next to the executable.

## The engine is not in this repository, and that is the point

`tests/test_motor_compartilhado.py` fails if any engine file is copied here, if an engine function
is redefined under another name, if the installed `pheno_engine` loads from inside this tree, or if
the pinned tag does not exist on the public remote. The map widgets, raster I/O and the point store
come from [`ts-annotator`](https://github.com/osmarluiz/ts-annotator); this repository is the
application — configuration, assembly, panels — and reimplements nothing.

## Citing

Cite this repository and pin both engines of the claim: this application and the `pheno-engine` tag
it installs. "The same engine" is only checkable if the reader knows which commit you mean.

## License

MIT.
