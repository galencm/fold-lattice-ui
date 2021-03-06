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

Setup linting and formatting git commit hooks:

```
cd fold-lattice-ui/
pre-commit install
pre-commit install -t commit-msg
```

## Usage

```
ma-ui-fold --size=1500x800
```

## Testing with fairytale

Fairytale is a program to generate structured and destructured test material for fold-ui

It is available on the commandline as `fold-ui-fairytale`

**Redis:**

Fairytale needs to connect to a redis server:

* _Testing or standalone without machinic_

  For testing, or if not using machinic a local redis server can be run with minimal setup(see below).

* _Machinic_

  If running other parts of the machinic ecosystem, a redis server is already running and fairytale will connect via service discovery.

If needed, redis can be installed from source or using a package manager:

on Fedora:

```
sudo dnf install redis
```

on Debian:

```
sudo apt-get install redis-server
```

**Fairytale examples:**

A simple example shows the creation of 600 items on a specified redis server (by default both fold-ui and fairytale will attempt to connect to redis via service discovery).

Create a config file to enable keyspace events and snapshot. Then start a redis server in the background:

```
printf "notify-keyspace-events KEA\nSAVE 60 1\n" >> redis.conf
redis-server redis.conf --port 6379 &
```

The server can be stopped with the command:
```
redis-cli -p 6379 shutdown
```

_Note: all examples use default redis port 6379, but any unused port can be substituted_


Run fairytale:

```
fold-ui-fairytale --db-host 127.0.0.1 --db-port 6379 --part-part-amounts 200 200 200 --part-increment-field page_number --part-field-values part part1 part2 part3 --verbose
```

Start fold-ui:

```
 fold-ui --size=1500x800 -- --db-host 127.0.0.1 --db-port 6379
```

A slightly more involved example:

* clear all previous keys matching `glworb:*` pattern
* generate 600 items with 300 disordered (out of sequence)
* items will expire in 1000 seconds
* enter items at an interval of 5 seconds

```
fold-ui-fairytale --db-host 127.0.0.1 --db-port 6379 --db-expire-in 1000 --part-part-amounts 200 200 200 --part-increment-field page_number --part-field-values part part1 part2 part3 --verbose --structure-stagger-delay 5 --structure-disorder 300 --db-del-pattern glworb:*
```

* roughly 300 items total in part1, part2, part3
* 2 missing
* 2 duplicates

```
fold-ui-fairytale --db-host 127.0.0.1 --db-port 6665 --db-expire-in 1000 --part-part-amounts 100 100 100 --part-increment-field page_number --part-field-values part part1 part2 part3 --verbose --structure-stagger-delay 0 --structure-disorder 300 --db-del-pattern glworb:* --db-del-field part --verbose --db-expire-interval 1 --structure-missing 2 --structure-duplicate 2
```

## Testing with boooks

Boooks are booklike structures used for testing in the machinic ecosystem. They may be useful as inputs for fold-ui.

Install [machinic-primitives-sources](https://github.com/galencm/machinic-primitives-sources) package with provides the cli command `primitives-generate-boook`:
```
pip3 install git+https://github.com/galencm/machinic-primitives-sources --user
```

Generate a collection of images and a manifest file in the `/tmp` directory.
```
cd /tmp
primitives-generate-boook --title boook --section foo 10 full --section bar 10 full --section baz 10 full --manifest csv --verbose
```

Ingest the csv data and images into a glworblike format recognized by fold-ui.  The argument and parameter `--ingest-map filename binary_key` maps the csv header `filename` to a key field of `binary_key`.

```
cd /tmp
fold-ui-fairytale --ingest-manifest boook.csv --ingest-map filename binary_key --ingest-as-binary filename --db-port 6379
```

For example, a boook with rotated images distinguished with fairytale by field _device_ containing _capture1_ or _capture2_:
```
primitives-generate-boook --section foo 10 full --section bar 10 full --section baz 10 full --manifest csv csv --verbose --rotate -90 90
```

```
fold-ui-fairytale --ingest-manifest boook.csv --ingest-map filename binary_key --ingest-as-binary filename --field-cycle device capture1 capture2 --db-port 6665 --db-del-pattern glworb:* --verbose
```

## Contributing
This project uses the C4 process 

[https://rfc.zeromq.org/spec:42/C4/](https://rfc.zeromq.org/spec:42/C4/
)

## License
Mozilla Public License, v. 2.0

[http://mozilla.org/MPL/2.0/](http://mozilla.org/MPL/2.0/)

