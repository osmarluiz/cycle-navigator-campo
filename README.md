# cycle-navigator

Read cropping systems as a **label-free continuum** instead of looking them up in a legend. The tool
queries the landscape by curve shape and recolours it along any phenometric axis, live and
region-wide.

It is the interactive counterpart of the paper *Navigating the cropping continuum* (see
[crop-continuum-paper](https://github.com/osmarluiz/crop-continuum-paper)). The paper's finding is that
cropping intensity holds no density gap where the one, two and three cycle classes are cut, and that the
threshold producing those classes is undecidable within a band that relabels a substantial share of the
map. A continuum has no legend to read off and an undecidable threshold has no single map worth
printing, so what is left is a reading the user moves. This is that reading.

## The engine is not in this repository, and that is the point

The paper claims that what a user drags here is the same code that produced its published numbers. That
claim holds only while the phenometric engine comes from the
[`ts-annotator`](https://github.com/osmarluiz/ts-annotator) package, pinned in `pyproject.toml`. This
repository is the **application**: configuration, assembly, entry point. It reimplements nothing.

`tests/test_motor_compartilhado.py` enforces it, and asks three separate questions:

1. is any engine file copied into this tree?
2. is any engine function redefined here under a different file name?
3. is the `pheno_engine` we import actually loaded from **outside** this tree?

The third exists because a stray `pheno.py` on the path would satisfy the first two and still break the
claim. Run them with `pytest`.

## Install

```bash
pip install -e ".[dev,pivots]"
```

`pivots` pulls `geopandas`, needed only to overlay a centre-pivot register. The tool opens without it.

## Configure

Paths are read from a file, never hard-coded. Copy `cycle-navigator.example.toml` to
`cycle-navigator.toml` and edit:

```toml
aoi   = "E:/sits_aoi_crop"
meses = [202210, 202211, 202212, 202301, 202302, 202303,
         202304, 202305, 202306, 202307, 202308, 202309]
```

The search order is `--config`, then `$CYCLE_NAVIGATOR_CONFIG`, then `./cycle-navigator.toml`, then
`~/.config/cycle-navigator/config.toml`. Every declared file is checked at start-up, so a wrong path
fails immediately with the offending name rather than thirty seconds into loading.

## Run

```bash
cycle-navigator                     # uses the config found by the search order
cycle-navigator --config other.toml
```

## Data

The tool reads a monthly satellite image time series over an area of interest: a twelve-month cube, a
few basemaps, and optionally a cropland prediction and a pivot register. It ships no data. The cube used
in the paper is a monthly PlanetScope series over the RIDE-DF in the Brazilian Cerrado.

## Citing

If you use this tool, cite the paper and pin the versions of **both** repositories, this one and
`ts-annotator`. "The same engine" is only checkable if the reader knows which commit you mean.

## License

MIT.
