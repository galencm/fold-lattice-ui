# fold-lattice-ui

_folded high level views and unfolded details of work-in-progress materials_

Quickly see groupings(current, roughly expected) and state of sequences(sequentiality, missing steps) that updates as new material is added. Custom palettes and patterns. Uses a folded columnar layout that can be unfolded to look at individual items or groups of items in detail.

## Installation

Pip:

```
pip3 install git+https://github.com/galencm/fold-lattice-ui --user --process-dependency-links
```

Develop while using pip:

```
git clone https://github.com/galencm/fold-lattice-ui
cd fold-lattice-ui/
pip3 install --editable ./ --user --process-dependency-links
```

## Usage

```
ma-ui-fold --size=1500x800
```

## Testing with fairytale

Fairytale is a program to generate structured and destructured test material for fold-ui

It is available on the commandline as `fold-ui-fairytale`

A simple example shows the creation of 600 items on a specified redis server (by default both fold-ui and fairytale will attempt to connect to redis via service discovery).

Start a redis server:

```
redis-server --port 6379
```

Run fairytale:

```
fold-ui-fairytale --db-host 127.0.0.1 --db-port 6379 --db-expire-in 400 --part-part-amounts 200 200 200 --part-increment-field page_number --part-field-values part part1 part2 part3 --verbose
```

Start fold-ui:

```
 fold-ui --size=1500x800 -- --db-host 127.0.0.1 --db-port 6379
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

