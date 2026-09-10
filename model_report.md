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
| Atlanta | 1.5 (-0.3) n=19 | 2.7 (+2.7) n=4 | 4.0 (+4.0) n=4 | 0.5 (-0.4) n=4 | 1.5 (+1.5) n=4 |
| Austin | 1.4 (-0.9) n=16 | 1.4 (-1.4) n=3 | 2.3 (-2.3) n=3 | 2.1 (-2.1) n=3 | 1.5 (-1.5) n=3 |
| Boston | 2.6 (-1.9) n=12 | 2.1 (+0.2) n=4 | 2.5 (+2.5) n=4 | 1.0 (-1.0) n=4 | 1.0 (+0.0) n=4 |
| Chicago | 1.5 (-1.2) n=15 | 2.2 (-2.2) n=3 | 0.6 (-0.6) n=3 | 0.7 (-0.7) n=3 | 2.5 (-2.5) n=3 |
| Dallas | 1.4 (-0.5) n=15 | 2.3 (-2.3) n=3 | 1.4 (-0.6) n=3 | 0.6 (-0.2) n=3 | 1.5 (-0.5) n=3 |
| Denver | 2.0 (-1.6) n=15 | 2.0 (-0.5) n=3 | 0.9 (-0.9) n=3 | 5.1 (-5.1) n=3 | 1.5 (-1.5) n=3 |
| Houston | 0.9 (+0.2) n=14 | 2.4 (-2.4) n=2 | 4.9 (+4.9) n=2 | 0.5 (+0.2) n=2 | 1.0 (+1.0) n=2 |
| Las Vegas | 1.6 (-0.7) n=16 | 0.9 (+0.9) n=3 | 1.0 (+0.1) n=3 | 2.5 (-2.5) n=3 | 0.5 (+0.5) n=3 |
| Los Angeles | 3.4 (+3.1) n=12 | 3.7 (-0.8) n=2 | 3.7 (-3.7) n=2 | 2.1 (+1.6) n=2 | 1.5 (+0.0) n=2 |
| Miami | 2.0 (-2.0) n=19 | 2.3 (-2.3) n=4 | 1.6 (+0.6) n=4 | 2.1 (-1.6) n=4 | 1.5 (+0.0) n=4 |
| Minneapolis | 1.4 (+0.0) n=11 | 1.8 (-1.8) n=2 | 4.5 (+4.5) n=2 | 3.5 (-3.5) n=2 | 1.0 (+1.0) n=2 |
| New Orleans | 1.7 (-1.1) n=15 | 2.3 (-2.3) n=3 | 2.4 (+2.4) n=3 | 2.4 (-2.4) n=3 | 0.5 (+0.5) n=3 |
| New York City | 2.5 (-0.9) n=12 | 4.6 (-4.6) n=2 | 2.4 (+1.4) n=2 | 0.8 (+0.5) n=2 | 1.5 (+0.0) n=2 |
| Oklahoma City | 1.5 (-1.0) n=13 | 0.9 (-0.4) n=3 | 1.6 (+1.6) n=3 | 0.5 (+0.0) n=3 | 1.5 (-1.5) n=3 |
| Philadelphia | 1.3 (-0.9) n=17 | 3.0 (-3.0) n=4 | 1.5 (-1.5) n=4 | 3.5 (-3.5) n=4 | 2.0 (-2.0) n=4 |
| Phoenix | 1.3 (-1.2) n=14 | 0.7 (-0.7) n=3 | 2.8 (-2.8) n=3 | 4.0 (-4.0) n=3 | 1.5 (-1.5) n=3 |
| San Antonio | 1.0 (-0.6) n=16 | 1.2 (-1.2) n=3 | 0.8 (-0.8) n=3 | 2.8 (-2.8) n=3 | 0.5 (-0.5) n=3 |
| San Francisco | 4.0 (+1.9) n=14 | 6.4 (-6.4) n=3 | 1.7 (-1.7) n=3 | 4.6 (-4.6) n=3 | 3.5 (-3.5) n=3 |
| Seattle | 2.5 (-1.6) n=14 | 2.5 (-2.5) n=2 | 4.0 (+4.0) n=2 | 3.6 (-3.6) n=2 | 1.0 (-0.5) n=2 |
| Washington DC | 1.5 (-0.2) n=16 | 1.5 (-0.5) n=4 | 1.6 (+1.6) n=4 | 4.0 (-4.0) n=4 | 0.5 (-0.5) n=4 |

## Overall (all cities pooled)

- **nws**: median miss 1.50F, lean -0.50F, n=60
- **pool**: median miss 1.60F, lean -0.70F, n=295
- **gfs**: median miss 2.15F, lean +0.40F, n=60
- **ecmwf**: median miss 2.20F, lean -1.55F, n=60
- **icon**: median miss 2.30F, lean -2.30F, n=60
