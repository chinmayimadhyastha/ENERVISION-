# Data Dictionary

## Plant-Weather Feature Dataset

| Column | Type | Description |
|---------|------|-------------|
| Date | Date | Observation date |
| PlantName | String | Renewable energy plant name |
| Type | String | Renewable energy type: Solar or Wind |
| Capacity_MW | Float | Installed plant capacity in megawatts (MW) |
| District | String | Karnataka district associated with the plant |
| Temperature | Float | Daily average temperature (°C) |
| Humidity | Float | Relative humidity (%) |
| WindSpeed | Float | Daily average wind speed (m/s) |
| GHI | Float | Global Horizontal Irradiance (kWh/m²/day) |
| Pressure | Float | Atmospheric pressure |
| Temperature_lag_1 | Float | Previous day's temperature |
| Humidity_lag_1 | Float | Previous day's humidity |
| WindSpeed_lag_1 | Float | Previous day's wind speed |
| GHI_lag_1 | Float | Previous day's GHI |
| Generation_lag_1 | Float | Previous day's energy generation (MU) |
| Generation_lag_2 | Float | Energy generation two days earlier (MU) |
| Generation_lag_3 | Float | Energy generation three days earlier (MU) |
| Generation_lag_7 | Float | Energy generation seven days earlier (MU) |
| Generation_roll_3 | Float | Three-day rolling mean of previous generation (MU) |
| Generation_roll_7 | Float | Seven-day rolling mean of previous generation (MU) |
| Generation_per_MW | Float | Energy generation normalized by installed capacity (MU/MW) |
| Year | Integer | Year of observation |
| Month | Integer | Month of observation |
| DayOfYear | Integer | Day number within the year |
| DayOfWeek | Integer | Day of week, where Monday = 0 |
| Month_sin | Float | Cyclic sine encoding of month |
| Month_cos | Float | Cyclic cosine encoding of month |
| DayOfYear_sin | Float | Cyclic sine encoding of day of year |
| DayOfYear_cos | Float | Cyclic cosine encoding of day of year |
| DailyGeneration_MU | Float | Actual daily energy generation in million units (MU); prediction target |
| _split | String | Dataset partition: train or test |