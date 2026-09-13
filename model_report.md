# Model report -- who forecasts each city best

Median miss (degrees F) between each model's night-before
forecast and the officially settled number, per city; the
signed lean in brackets (+ runs hot, - runs cold). `pool` is
the calibrated GFS+ECMWF median the money actually used;
`gfs`/`ecmwf` are its two voters graded separately (also
calibrated); `icon`/`nws` are raw research passengers riding
along -- a passenger that ties the calibrated incumbents is
doing well. Small n means luck still speaks louder than
skill. RESEARCH ONLY: no trading or calibration code reads
this file, and promotion of any model into the vote is an
owner decision. Regenerated in full by model_report.py.

| city | pool | ecmwf | gfs | icon | nws |
|---|---|---|---|---|---|
| Atlanta | 1.5 (-0.3) n=21 | 2.6 (+1.6) n=6 | 3.4 (+3.4) n=6 | 0.8 (-0.8) n=6 | 2.0 (+2.0) n=6 |
| Austin | 1.4 (-1.0) n=19 | 1.2 (-1.2) n=6 | 1.9 (-1.9) n=6 | 2.8 (-2.8) n=6 | 1.5 (-1.5) n=6 |
| Boston | 2.4 (-2.1) n=14 | 2.1 (-1.5) n=6 | 1.8 (+1.4) n=6 | 2.0 (-2.0) n=6 | 2.0 (-1.0) n=6 |
| Chicago | 1.5 (-0.5) n=18 | 2.0 (-0.5) n=6 | 2.4 (+1.6) n=6 | 1.1 (-0.4) n=6 | 2.0 (-0.5) n=6 |
| Dallas | 1.5 (-0.9) n=18 | 2.5 (-2.5) n=6 | 0.8 (-0.0) n=6 | 0.9 (-0.8) n=6 | 1.5 (-1.0) n=6 |
| Denver | 1.7 (-1.2) n=18 | 1.6 (+1.1) n=6 | 0.9 (-0.7) n=6 | 1.5 (-1.5) n=6 | 1.5 (-1.0) n=6 |
| Houston | 1.3 (-0.4) n=17 | 3.0 (-3.0) n=5 | 2.3 (+2.3) n=5 | 0.7 (-0.2) n=5 | 1.5 (+0.5) n=5 |
| Las Vegas | 1.8 (-0.6) n=19 | 1.0 (+1.0) n=6 | 1.0 (-1.0) n=6 | 2.6 (-2.6) n=6 | 0.5 (+0.0) n=6 |
| Los Angeles | 3.2 (+3.1) n=13 | 3.2 (+2.9) n=3 | 3.9 (-3.9) n=3 | 1.2 (-0.4) n=3 | 1.5 (+1.5) n=3 |
| Miami | 2.1 (-1.8) n=22 | 1.5 (-1.4) n=7 | 2.1 (+2.1) n=7 | 3.0 (-3.0) n=7 | 1.5 (+0.5) n=7 |
| Minneapolis | 1.6 (+0.5) n=14 | 1.0 (-1.0) n=5 | 5.4 (+5.4) n=5 | 3.0 (-3.0) n=5 | 0.5 (+0.5) n=5 |
| New Orleans | 1.6 (-0.7) n=17 | 1.8 (-1.8) n=5 | 2.7 (+2.7) n=5 | 2.3 (-2.3) n=5 | 0.5 (+0.5) n=5 |
| New York City | 2.4 (-1.4) n=14 | 3.4 (-3.4) n=4 | 1.6 (-0.3) n=4 | 0.4 (-0.1) n=4 | 1.5 (+1.0) n=4 |
| Oklahoma City | 1.6 (-1.0) n=15 | 1.5 (-0.4) n=5 | 1.6 (+1.6) n=5 | 0.5 (+0.0) n=5 | 1.5 (-1.5) n=5 |
| Philadelphia | 1.4 (-0.8) n=20 | 3.0 (-1.2) n=7 | 1.5 (-1.2) n=7 | 2.5 (-2.5) n=7 | 1.5 (-1.5) n=7 |
| Phoenix | 1.3 (-1.0) n=17 | 0.8 (-0.1) n=6 | 0.8 (-0.7) n=6 | 3.0 (-3.0) n=6 | 1.5 (+0.5) n=6 |
| San Antonio | 1.0 (-0.7) n=19 | 1.2 (-0.9) n=6 | 1.3 (-1.3) n=6 | 1.4 (-0.9) n=6 | 0.5 (-0.5) n=6 |
| San Francisco | 4.1 (+2.1) n=15 | 5.4 (-5.4) n=4 | 3.1 (-0.1) n=4 | 4.3 (-4.3) n=4 | 3.0 (-3.0) n=4 |
| Seattle | 2.2 (-0.9) n=17 | 2.8 (-2.3) n=5 | 2.3 (+2.3) n=5 | 3.0 (-3.0) n=5 | 1.5 (-0.5) n=5 |
| Washington DC | 1.5 (+0.7) n=19 | 1.6 (+0.5) n=7 | 1.8 (+0.6) n=7 | 3.2 (-3.2) n=7 | 0.5 (-0.5) n=7 |

## Overall (all cities pooled)

- **nws**: median miss 1.50F, lean -0.50F, n=111
- **pool**: median miss 1.60F, lean -0.70F, n=346
- **ecmwf**: median miss 1.90F, lean -1.10F, n=111
- **gfs**: median miss 2.00F, lean +0.50F, n=111
- **icon**: median miss 2.10F, lean -1.90F, n=111
