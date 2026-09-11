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
| Atlanta | 1.5 (-0.3) n=20 | 1.9 (+1.9) n=5 | 3.6 (+3.6) n=5 | 0.5 (-0.5) n=5 | 1.5 (+1.5) n=5 |
| Austin | 1.4 (-0.9) n=18 | 1.1 (-1.1) n=5 | 2.3 (-2.3) n=5 | 2.3 (-2.3) n=5 | 1.5 (-1.5) n=5 |
| Boston | 2.5 (-2.2) n=13 | 2.5 (-1.3) n=5 | 1.6 (+1.6) n=5 | 1.3 (-1.3) n=5 | 1.5 (-0.5) n=5 |
| Chicago | 1.6 (-0.6) n=17 | 2.2 (-0.6) n=5 | 2.1 (+0.6) n=5 | 1.5 (-0.7) n=5 | 2.5 (+0.5) n=5 |
| Dallas | 1.4 (-0.5) n=17 | 2.3 (-2.3) n=5 | 0.9 (-0.3) n=5 | 0.6 (-0.2) n=5 | 1.5 (-0.5) n=5 |
| Denver | 1.8 (-1.3) n=17 | 1.6 (+0.7) n=5 | 0.9 (-0.9) n=5 | 1.5 (-1.5) n=5 | 1.5 (-1.5) n=5 |
| Houston | 1.0 (-0.1) n=16 | 2.8 (-2.8) n=4 | 3.4 (+3.4) n=4 | 0.6 (+0.2) n=4 | 1.0 (+1.0) n=4 |
| Las Vegas | 1.4 (-0.4) n=18 | 1.0 (+1.0) n=5 | 1.0 (-0.9) n=5 | 2.5 (-2.5) n=5 | 0.5 (+0.5) n=5 |
| Los Angeles | 3.4 (+3.1) n=12 | 3.7 (-0.8) n=2 | 3.7 (-3.7) n=2 | 2.1 (+1.6) n=2 | 1.5 (+0.0) n=2 |
| Miami | 2.0 (-1.8) n=20 | 1.4 (-1.4) n=5 | 2.1 (+2.1) n=5 | 3.0 (-3.0) n=5 | 1.5 (+0.5) n=5 |
| Minneapolis | 1.4 (+0.0) n=13 | 1.8 (-1.8) n=4 | 4.9 (+4.9) n=4 | 3.2 (-3.2) n=4 | 0.5 (+0.5) n=4 |
| New Orleans | 1.6 (-0.9) n=16 | 2.0 (-2.0) n=4 | 2.6 (+2.6) n=4 | 2.4 (-2.4) n=4 | 0.5 (+0.5) n=4 |
| New York City | 2.5 (-0.9) n=12 | 4.6 (-4.6) n=2 | 2.4 (+1.4) n=2 | 0.8 (+0.5) n=2 | 1.5 (+0.0) n=2 |
| Oklahoma City | 1.6 (-1.0) n=15 | 1.5 (-0.4) n=5 | 1.6 (+1.6) n=5 | 0.5 (+0.0) n=5 | 1.5 (-1.5) n=5 |
| Philadelphia | 1.2 (-1.0) n=18 | 3.0 (-3.0) n=5 | 1.5 (-1.5) n=5 | 4.6 (-4.6) n=5 | 2.5 (-2.5) n=5 |
| Phoenix | 1.3 (-1.0) n=16 | 0.7 (-0.6) n=5 | 0.9 (-0.9) n=5 | 3.3 (-3.3) n=5 | 1.5 (-0.5) n=5 |
| San Antonio | 1.0 (-0.7) n=18 | 1.2 (-1.2) n=5 | 1.8 (-1.8) n=5 | 1.5 (-1.5) n=5 | 0.5 (-0.5) n=5 |
| San Francisco | 4.0 (+1.9) n=14 | 6.4 (-6.4) n=3 | 1.7 (-1.7) n=3 | 4.6 (-4.6) n=3 | 3.5 (-3.5) n=3 |
| Seattle | 2.1 (-1.4) n=16 | 2.5 (-2.5) n=4 | 2.2 (+2.2) n=4 | 3.6 (-3.6) n=4 | 1.0 (-1.0) n=4 |
| Washington DC | 1.5 (-1.2) n=17 | 1.6 (-1.6) n=5 | 2.2 (+0.6) n=5 | 4.7 (-4.7) n=5 | 0.5 (-0.5) n=5 |

## Overall (all cities pooled)

- **nws**: median miss 1.50F, lean -0.50F, n=88
- **pool**: median miss 1.60F, lean -0.70F, n=323
- **ecmwf**: median miss 1.85F, lean -1.25F, n=88
- **gfs**: median miss 2.05F, lean +0.40F, n=88
- **icon**: median miss 2.20F, lean -2.10F, n=88
