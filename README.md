Case for a split 40% Alice keyboard, designed with [alice-layout-designer](https://github.com/Noah-Mav/alice-layout-designer.git)

![Alice case in walnut with Cherry-profile keycaps](docs/images/hero_iso.png)

| Top | Back | Underside | Low |
|---|---|---|---|
| ![Top view](docs/images/top.png) | ![Back view with USB-C](docs/images/back.png) | ![Underside](docs/images/underside.png) | ![Low three-quarter view](docs/images/low.png) |

Renders from Fusion (walnut body, anodised panel, Cherry-profile caps). Electronics are placeholders.

The layout designer is included as the `layout/` submodule (`layout/alice.py` supplies the key positions). The saved layout is `layouts/layout2.json`.

## Clone

```
git clone --recurse-submodules https://github.com/Noah-Mav/alice-case
# already cloned without it:
git submodule update --init
```

## Where to look

- [case/README.md](case/README.md): setup (venv), running the geometry and tests, Fusion build and export.
- [docs/fusion-case-plan.md](docs/fusion-case-plan.md): the case design plan.
