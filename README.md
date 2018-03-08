# fold-lattice-ui

_folded high level views and unfolded details of work-in-progress materials_

Quickly see groupings(current, roughly expected) and state of sequences(sequentiality, missing steps) that updates as new material is added. Custom palettes and patterns. Uses a folded columnar layout that can be unfolded to look at individual items or groups of items in detail.

## Usage

basic:
```
python3 fold_lattice_ui.py --size=1500x800
```

change window size and create/save palette(notice double dash -- separating cli args from kivy args):
```
python3 fold_lattice_ui.py --size=1500x800  -- --filter-key source_uid --palette '{"roman": { "border":"black", "fill": [155,155,255,1]}}' --palette-name foo
```

visually sketch groups (values for field)
```
python3 fold_lattice_ui.py --size=1500x800 -- --group-sketch '{"chapter" : {"part1":60,"part2":60}}'
```

## Keybindings:

Up/Down: move view up or down a row in unfolded fold

Left/Right: move view back or forward a column in unfolded fold

Ctrl-Up: increase item size in all folds

Ctrl-Down: decrease item size in all folds

Ctrl-Left: increase columns / decrease rows

Ctrl-Right: increase rows / decrease columns

Shift-Left: unfold to left

Shift-Right: unfold to right

Shift-Up: increase item size in unfolded fold

Shift-Down: decrease item size in unfolded fold

Ctrl-C: exit

## Contributing
This project uses the C4 process 

[https://rfc.zeromq.org/spec:42/C4/](https://rfc.zeromq.org/spec:42/C4/
)

## License
Mozilla Public License, v. 2.0

[http://mozilla.org/MPL/2.0/](http://mozilla.org/MPL/2.0/)

