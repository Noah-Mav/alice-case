# PCB for the v3 case

What a real pair of PCBs needs so that both halves work and fit the v3 case. The files here come from `case/pcb_export.py`, which reads the case geometry, so they always match the case.

## How the halves connect

The daughterboard has one 4-pin output, so the connection is a chain:

```
USB-C ── daughterboard ──(4-pin, 1:1)──► LEFT PCB (MCU) ──(4-pin, 1:1)──► RIGHT PCB (MCU)
          (in the bay)                     2 headers                       1 header
```

- **Left PCB:** the main half. It has the MCU, and USB comes in from the daughterboard on header 1. Header 2 goes to the right half.
- **Right PCB:** the same kind of board, with its own MCU, and one header to the left half.
- **Firmware:** QMK split (or Vial). The left half talks to the computer; the two halves talk over a single-wire serial link on the 4-pin cable.
- **Cables:** both run through the case's existing cable channels into the daughterboard bay, then on to the left half's headers.

**Why an MCU on each half:** the right half then needs only 4 wires (5 V, GND, data, plus a spare), so it can use the same small connector the case is already cut for. The other way, running the right half's whole key matrix over the cable, needs about 10 wires and a bigger connector on both halves.

## Connectors and cables

| | Part | Pins (1 to 4) |
|---|---|---|
| Daughterboard output | JST-SH 4-pin on the C3 (SM04B-SRSS-TB). C4 / C5 use Molex Pico-EZmate (781710004); same board size, so the case fits either | **1 VBUS (5 V), 2 D−, 3 D+, 4 GND** (from the C3 KiCad source) |
| Left header 1 (USB in) | Same family as your daughterboard, with **the same pinout, not mirrored** (the cable is 1:1) | 1 VBUS, 2 D−, 3 D+, 4 GND |
| Left header 2 (link) | JST-SH 4-pin, **vertical** (BM04B-SRSS-TB): the plug goes straight down into the case's cable cutout, so it never meets header 1 | 1 VBUS (5 V), 2 serial data, 3 spare (or the second serial line), 4 GND |
| Right header (link) | JST-SH 4-pin, SM04B-SRSS-TB (side entry, like header 1) | same as left header 2 |

- **Power on the same pins everywhere.** VBUS is on pin 1 and GND on pin 4 on every header. If a cable goes into the wrong header, nothing gets damaged.
- **Cables:** use 4-pin cables wired 1:1 (pin 1 to pin 1). Buy them ready-made, or make them to length from a 4-pin housing (JST-SH: SHR-04V-S-B) and pre-crimped wires. The daughterboard docs list the parts for the Pico-EZmate version. About 100 mm each leaves slack to tuck into the bay: each header is about 20 to 25 mm from the bay in plan, plus the drops.

## Design rules from the case

| Rule | Value |
|---|---|
| Board | 2-layer FR4, **1.6 mm** thick (the gaskets' slot is made for 1.6) |
| Outline | `left_outline.dxf` / `right_outline.dxf`, layer `EDGE`: import into Edge.Cuts. The plate uses the same edge |
| Switches | MX, plate-mounted (the plate is 5.0 mm above the PCB top), Kailh CPG151101S11 hotswap sockets on the bottom. Key centres and rotations: `left_keys.csv` / `right_keys.csv` (KiCad frame: y down, rotation counter-clockwise from the top) |
| Stabilizers | plate-mounted, at the `STAB` outlines (2u keys); keep the PCB stab holes |
| Gasket zones | layer `CLIP_KEEPOUT`, 10 zones (5 per half): **no parts or pads** within 3 mm of the edge there on either face. The TPU gaskets grip the board edge |
| Edge band | keep all parts at least 1 mm in from the edge everywhere (the wall is 0.9 mm away) |
| Bottom parts | **2.5 mm tall at most** (3.5 mm of air under the board, 1 mm margin). The sockets sit over the floor grooves. Keep parts off the socket outlines and the switch centre posts |
| Top parts | none between the switches (the plate and switch housings fill that space) |
| Header 1 | the `CONNECTOR` outline, at the inner back corner of each half. The case's breakthrough to the bay is under it, so keep the header there, facing the bay |
| Header 2 (left only) | the `CONNECTOR_2` outline, just outboard of header 1 (pocket x 102.8 to 108.8, y 60.1 to 68.1), clear of the sockets. A vertical header, so its plug enters from below; the case's cable cutout is cut round both headers |
| MCU space | the largest clear square on the bottom of each half is about **10 x 10 mm** (90+ spots between the sockets) |

## Parts per half

- **MCU:** STM32F072CBU6 (QFN-48, 7 x 7 mm). It needs no crystal for USB and has flash built in, so it fits one 10 x 10 mm spot with its capacitors and a 3.3 V regulator. An RP2040 works too, but its flash chip and crystal need a second spot. QMK supports both for split boards.
- **3.3 V regulator:** SOT-23-5 LDO (for example AP2112K-3.3) from VBUS.
- **Keys:** 21 (left) and 20 (right). One 1N4148W (SOD-123) diode per key, plus the hotswap sockets.
- **Matrix:** 5 x 5 on each half fits easily (the STM32F072 has about 37 free I/O).
- **Programming:** SWD test pads and a BOOT0 pad or button, both on the bottom away from the gasket zones.
- **Protection:** the daughterboard has ESD and overcurrent protection on board, so the main PCB can stay simple (per the daughterboard docs).

## Steps in KiCad

1. Import `<half>_outline.dxf` into Edge.Cuts (File > Import > Graphics, mm). Put `CLIP_KEEPOUT`, `CONNECTOR`, `CONNECTOR_2` and `STAB` on a user layer as guides.
2. Place the switch, socket and diode footprints at the `<half>_keys.csv` positions (a short KiCad Python script or a placement plugin can read the CSV).
3. Put header 1 on the `CONNECTOR` outline, and on the left half header 2 on `CONNECTOR_2`. Then put the MCU, regulator and capacitors in the clear spots on the bottom.
4. Before ordering, check the board against the v3 dummy PCB print (`prints/v3/dummy_pcb_*.stl`). They share the same outline.
