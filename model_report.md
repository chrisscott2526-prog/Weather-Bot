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
| Austin | 1.4 (-0.9) n=20 | 1.4 (-1.1) n=7 | 2.3 (-1.6) n=7 | 2.3 (-2.3) n=7 | 1.5 (-1.5) n=7 |
| Boston | 2.4 (-2.1) n=14 | 2.1 (-1.5) n=6 | 1.8 (+1.4) n=6 | 2.0 (-2.0) n=6 | 2.0 (-1.0) n=6 |
| Chicago | 1.6 (-0.6) n=19 | 2.2 (-0.6) n=7 | 2.1 (+0.6) n=7 | 1.5 (-0.7) n=7 | 2.5 (-1.5) n=7 |
| Dallas | 1.4 (-0.5) n=19 | 2.3 (-2.3) n=7 | 0.9 (+0.2) n=7 | 1.3 (-0.2) n=7 | 1.5 (-0.5) n=7 |
| Denver | 1.7 (-1.2) n=18 | 1.6 (+1.1) n=6 | 0.9 (-0.7) n=6 | 1.5 (-1.5) n=6 | 1.5 (-1.0) n=6 |
| Houston | 1.4 (-0.4) n=18 | 3.7 (-3.7) n=6 | 2.2 (+2.2) n=6 | 1.0 (-0.8) n=6 | 1.5 (+0.5) n=6 |
| Las Vegas | 1.5 (-0.4) n=20 | 1.1 (+1.0) n=7 | 1.0 (-0.9) n=7 | 2.5 (-2.5) n=7 | 0.5 (+0.5) n=7 |
| Los Angeles | 3.1 (+2.8) n=14 | 3.1 (+2.8) n=4 | 4.7 (-4.7) n=4 | 1.1 (-0.7) n=4 | 1.5 (+1.5) n=4 |
| Miami | 2.1 (-1.8) n=22 | 1.5 (-1.4) n=7 | 2.1 (+2.1) n=7 | 3.0 (-3.0) n=7 | 1.5 (+0.5) n=7 |
| Minneapolis | 1.4 (+0.0) n=15 | 1.7 (-1.7) n=6 | 4.9 (+4.9) n=6 | 3.2 (-3.2) n=6 | 0.5 (+0.5) n=6 |
| New Orleans | 1.6 (-0.6) n=18 | 1.3 (-1.2) n=6 | 3.4 (+3.4) n=6 | 2.4 (-2.4) n=6 | 0.5 (+0.5) n=6 |
| New York City | 2.4 (-1.4) n=14 | 3.4 (-3.4) n=4 | 1.6 (-0.3) n=4 | 0.4 (-0.1) n=4 | 1.5 (+1.0) n=4 |
| Oklahoma City | 1.6 (-1.0) n=15 | 1.5 (-0.4) n=5 | 1.6 (+1.6) n=5 | 0.5 (+0.0) n=5 | 1.5 (-1.5) n=5 |
| Philadelphia | 1.4 (-0.8) n=20 | 3.0 (-1.2) n=7 | 1.5 (-1.2) n=7 | 2.5 (-2.5) n=7 | 1.5 (-1.5) n=7 |
| Phoenix | 1.3 (-1.0) n=18 | 0.9 (-0.6) n=7 | 0.9 (-0.9) n=7 | 3.3 (-3.3) n=7 | 1.5 (+0.5) n=7 |
| San Antonio | 1.0 (-0.6) n=20 | 1.2 (-0.5) n=7 | 1.8 (-0.8) n=7 | 1.5 (-0.3) n=7 | 0.5 (-0.5) n=7 |
| San Francisco | 4.0 (+1.9) n=16 | 4.3 (-4.3) n=5 | 1.7 (+1.0) n=5 | 4.6 (-4.6) n=5 | 2.5 (-2.5) n=5 |
| Seattle | 2.5 (-0.9) n=18 | 2.8 (-2.1) n=6 | 3.5 (+3.5) n=6 | 2.6 (-2.6) n=6 | 1.5 (+0.0) n=6 |
| Washington DC | 1.5 (+0.7) n=19 | 1.6 (+0.5) n=7 | 1.8 (+0.6) n=7 | 3.2 (-3.2) n=7 | 0.5 (-0.5) n=7 |

## Overall (all cities pooled)

- **nws**: median miss 1.50F, lean -0.50F, n=123
- **pool**: median miss 1.60F, lean -0.70F, n=358
- **ecmwf**: median miss 1.90F, lean -1.10F, n=123
- **gfs**: median miss 2.00F, lean +0.60F, n=123
- **icon**: median miss 2.10F, lean -1.90F, n=123
