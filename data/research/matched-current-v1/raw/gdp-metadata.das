Attributes {
 s {
  ID {
    String cf_role "trajectory_id";
    String ioos_category "Identifier";
    String long_name "Global Drifter Program Buoy ID";
  }
  WMO {
    Int32 _FillValue -999999;
    Int32 actual_range 0, 8800888;
    Float64 colorBarMaximum 100.0;
    Float64 colorBarMinimum 0.0;
    String history "From dirall.dat";
    String long_name "World Meteorological Organization buoy identification number";
    Int32 missing_value -999;
  }
  expno {
    Int32 _FillValue -999999;
    Int32 actual_range 46, 32212;
    Float64 colorBarMaximum 100.0;
    Float64 colorBarMinimum 0.0;
    String history "From dirall.dat";
    String long_name "Experiment number";
    Int32 missing_value -999;
    String units "count";
  }
  time {
    String _CoordinateAxisType "Time";
    Float64 actual_range 5.60178e+8, 1.6671744e+9;
    String axis "T";
    Float64 colorBarMaximum 100.0;
    Float64 colorBarMinimum -100.0;
    String ioos_category "Time";
    String long_name "Time";
    String standard_name "time";
    String time_origin "01-JAN-1970 00:00:00";
    String units "seconds since 1970-01-01T00:00:00Z";
    Float64 valid_max 3.0e+10;
    Float64 valid_min 2.0e+8;
  }
  latitude {
    String _CoordinateAxisType "Lat";
    Float32 _FillValue -999999.0;
    Float32 actual_range -78.30718, 89.98403;
    String axis "Y";
    Float64 colorBarMaximum 90.0;
    Float64 colorBarMinimum -90.0;
    String ioos_category "Location";
    String long_name "Latitude";
    Float32 missing_value -1.0e+34;
    String standard_name "latitude";
    String units "degrees_north";
    Float32 valid_max 90.0;
    Float32 valid_min -90.0;
  }
  longitude {
    String _CoordinateAxisType "Lon";
    Float32 _FillValue -999999.0;
    Float32 actual_range -180.0, 180.0;
    String axis "X";
    Float64 colorBarMaximum 180.0;
    Float64 colorBarMinimum -180.0;
    String ioos_category "Location";
    String long_name "Longitude";
    Float32 missing_value -1.0e+34;
    String standard_name "longitude";
    String units "degrees_east";
    Float32 valid_max 180.0;
    Float32 valid_min -180.0;
  }
  lon360 {
    Float32 _FillValue -999999.0;
    Float32 actual_range 0.0, 360.0;
    String axis "X";
    Float64 colorBarMaximum 180.0;
    Float64 colorBarMinimum -180.0;
    String long_name "Longitude";
    Float32 missing_value -1.0e+34;
    String standard_name "longitude";
    String units "degrees_east";
    Float32 valid_max 360.0;
    Float32 valid_min 0.0;
  }
  sst {
    Float64 _FillValue -999999.0;
    Float64 actual_range -998.8399625853385, 6935.946145480505;
    Float64 colorBarMaximum 305.0;
    Float64 colorBarMinimum 273.0;
    String ioos_category "Temperature";
    String long_name "fitted sea water temperature";
    Float64 missing_value -1.0e+34;
    String standard_name "sea_water_temperature";
    String units "Kelvin";
  }
  sst1 {
    Float64 _FillValue -999999.0;
    Float64 actual_range -993.218203606482, 5078.501466679307;
    Float64 colorBarMaximum 305.0;
    Float64 colorBarMinimum 273.0;
    String ioos_category "Temperature";
    String long_name "fitted non-diurnal sea water temperature";
    Float64 missing_value -1.0e+34;
    String standard_name "sea_water_temperature";
    String units "Kelvin";
  }
  sst2 {
    Float64 _FillValue -999999.0;
    Float64 actual_range -998.5294141049665, 5212.662006261129;
    Float64 colorBarMaximum 3.0;
    Float64 colorBarMinimum -3.0;
    String ioos_category "Temperature";
    String long_name "fitted diurnal sea water temperature";
    Float64 missing_value -1.0e+34;
    String standard_name "surface_temperature_anomaly";
    String units "Kelvin";
  }
  err_sst {
    Float64 _FillValue -999999.0;
    Float64 actual_range 1.316919246718948e-4, 12403.336234337685;
    Float64 colorBarMaximum 305.0;
    Float64 colorBarMinimum 273.0;
    String ioos_category "Quality";
    String long_name "standard uncertainty of fitted sea water temperature";
    Float64 missing_value -1.0e+34;
    String standard_name "sea_water_temperature";
    String units "Kelvin";
  }
  err_sst1 {
    Float64 _FillValue -999999.0;
    Float64 actual_range 5.060282444099445e-5, 5630.134683892944;
    Float64 colorBarMaximum 305.0;
    Float64 colorBarMinimum 273.0;
    String ioos_category "Quality";
    String long_name "standard uncertainty of fitted non-diurnal sea water temperature";
    Float64 missing_value -1.0e+34;
    String standard_name "sea_water_temperature";
    String units "Kelvin";
  }
  err_sst2 {
    Float64 _FillValue -999999.0;
    Float64 actual_range 1.2937428182201066e-4, 7336.699895774796;
    Float64 colorBarMaximum 3.0;
    Float64 colorBarMinimum -3.0;
    String ioos_category "Quality";
    String long_name "standard uncertainty of fitted diurnal sea water temperature";
    Float64 missing_value -1.0e+34;
    String standard_name "surface_temperature_anomaly";
    String units "Kelvin";
  }
  flg_sst {
    Float64 _FillValue -999999.0;
    Float64 actual_range 0.0, 5.0;
    Float64 colorBarMaximum 6.0;
    Float64 colorBarMinimum 0.0;
    String flag_meanings "no-estimate, no-uncertainty-estimate, estimate-not-in-range-uncertainty-not-in-range, estimate-not-in-range-uncertainty-in-range, estimate-in-range-uncertainty-not-in-range, estimate-in-range-uncertainty-in-range";
    String flag_values "0, 1, 2, 3, 4, 5";
    String ioos_category "Quality";
    String long_name "fitted sea water temperature quality flag";
    Float64 missing_value -999999.0;
    String standard_name "quality flag";
    String units "dimensionless";
  }
  flg_sst1 {
    Float64 _FillValue -999999.0;
    Float64 actual_range 0.0, 5.0;
    Float64 colorBarMaximum 6.0;
    Float64 colorBarMinimum 0.0;
    String flag_meanings "no-estimate, no-uncertainty-estimate, estimate-not-in-range-uncertainty-not-in-range, estimate-not-in-range-uncertainty-in-range, estimate-in-range-uncertainty-not-in-range, estimate-in-range-uncertainty-in-range";
    String flag_values "0, 1, 2, 3, 4, 5";
    String ioos_category "Quality";
    String long_name "fitted non-diurnal sea water temperature quality flag";
    Float64 missing_value -999999.0;
    String standard_name "quality flag";
    String units "dimensionless";
  }
  flg_sst2 {
    Float64 _FillValue -999999.0;
    Float64 actual_range 0.0, 5.0;
    Float64 colorBarMaximum 6.0;
    Float64 colorBarMinimum 0.0;
    String flag_meanings "no-estimate, no-uncertainty-estimate, estimate-not-in-range-uncertainty-not-in-range, estimate-not-in-range-uncertainty-in-range, estimate-in-range-uncertainty-not-in-range, estimate-in-range-uncertainty-in-range";
    String flag_values "0, 1, 2, 3, 4, 5";
    String ioos_category "Quality";
    String long_name "fitted diurnal sea water temperature quality flag";
    Float64 missing_value -999999.0;
    String standard_name "quality flag";
    String units "dimensionless";
  }
  ve {
    Float32 _FillValue -999999.0;
    Float32 actual_range -8.3641, 50.15901;
    Float64 colorBarMaximum 0.5;
    Float64 colorBarMinimum -0.5;
    String long_name "Eastward velocity";
    Float32 missing_value -1.0e+34;
    String standard_name "surface_eastward_sea_water_velocity";
    String units "m/s";
  }
  vn {
    Float32 _FillValue -999999.0;
    Float32 actual_range -8.864425, 12.57357;
    Float64 colorBarMaximum 0.5;
    Float64 colorBarMinimum -0.5;
    String long_name "Northward velocity";
    Float32 missing_value -1.0e+34;
    String standard_name "surface_northward_sea_water_velocity";
    String units "m/s";
  }
  err_lat {
    Float32 _FillValue -999999.0;
    Float32 actual_range -9.99999, 0.13652;
    Float64 colorBarMaximum 50.0;
    Float64 colorBarMinimum 0.0;
    String long_name "95% confidence interval in latitude";
    Float32 missing_value -1.0e+34;
    String units "degrees_north";
  }
  err_lon {
    Float32 _FillValue -999999.0;
    Float32 actual_range 9.9999994e-11, 0.003599995;
    Float64 colorBarMaximum 50.0;
    Float64 colorBarMinimum 0.0;
    String long_name "95% confidence interval in longitude";
    Float32 missing_value -1.0e+34;
    String units "degrees_east";
  }
  err_ve {
    Float32 _FillValue -999999.0;
    Float32 actual_range 1.8201085e-7, 47.3575;
    Float64 colorBarMaximum 50.0;
    Float64 colorBarMinimum 0.0;
    String long_name "95% confidence interval in eastward velocity";
    Float32 missing_value -1.0e+34;
    String units "m/s";
  }
  err_vn {
    Float32 _FillValue -999999.0;
    Float32 actual_range 1.8201085e-7, 6.6311;
    Float64 colorBarMaximum 50.0;
    Float64 colorBarMinimum 0.0;
    String long_name "95% confidence interval in northward velocity";
    Float32 missing_value -1.0e+34;
    String units "m/s";
  }
  typebuoy {
    String history "From directory file dirall.dat";
    String long_name "Buoy type (see https://www.aoml.noaa.gov/phod/dac/dirall.html)";
  }
  gap {
    Float32 _FillValue -999999.0;
    Float32 actual_range 0.0, 43200.0;
    String long_name "time interval between previous and next location fix";
    Float32 missing_value -1.0e+34;
    String units "seconds";
  }
  deploy_date {
    Float64 actual_range 5.601312e+8, 1.6670016e+9;
    String history "From deployment log deplog.dat";
    String ioos_category "Time";
    String long_name "Deployment date and time";
    String standard_name "time";
    String time_origin "01-JAN-1970 00:00:00";
    String units "seconds since 1970-01-01T00:00:00Z";
  }
  deploy_lat {
    Float64 _FillValue -999999.0;
    Float64 actual_range -77.81, 89.9;
    Float64 colorBarMaximum 90.0;
    Float64 colorBarMinimum -90.0;
    String history "From deployment log deplog.dat";
    String long_name "Deployment latitude";
    Float64 missing_value -1.0e+34;
    String units "degrees_north";
  }
  deploy_lon {
    Float64 _FillValue -999999.0;
    Float64 actual_range -180.0, 180.0;
    Float64 colorBarMaximum 180.0;
    Float64 colorBarMinimum -180.0;
    String history "From deployment log deplog.dat";
    String long_name "Deployment longitude";
    Float64 missing_value -1.0e+34;
    String units "degrees_east";
  }
  end_date {
    Float64 actual_range 5.626368e+8, 1.6862688e+9;
    String history "From directory file dirall.dat";
    String ioos_category "Time";
    String long_name "Last good date and time derived by DAC quality control";
    String standard_name "time";
    String time_origin "01-JAN-1970 00:00:00";
    String units "seconds since 1970-01-01T00:00:00Z";
  }
  end_lat {
    Float64 _FillValue -999999.0;
    Float64 actual_range -77.49, 99.54;
    Float64 colorBarMaximum 90.0;
    Float64 colorBarMinimum -90.0;
    String history "From directory file dirall.dat";
    String long_name "Last good latitude derived by DAC quality control";
    Float64 missing_value -1.0e+34;
    String units "degrees_north";
  }
  end_lon {
    Float64 _FillValue -999999.0;
    Float64 actual_range -179.99, 179.98;
    Float64 colorBarMaximum 180.0;
    Float64 colorBarMinimum -180.0;
    String history "From directory file dirall.dat";
    String long_name "Last good longitude derived by DAC quality control";
    Float64 missing_value -1.0e+34;
    String units "degrees_east";
  }
  drogue_lost_date {
    Float64 actual_range 0.0, 1.6854048e+9;
    String history "From directory file dirall.dat";
    String ioos_category "Time";
    String long_name "Date of drogue loss (FillValue=drogue still attached; 0=drogue status uncertain from beginning)";
    String standard_name "time";
    String time_origin "01-JAN-1970 00:00:00";
    String units "seconds since 1970-01-01T00:00:00Z";
  }
  typedeath {
    Int32 _FillValue -999999;
    Int32 actual_range 0, 6;
    String history "From directory file dirall.dat";
    String long_name "Type of death (0=buoy still alive, 1=buoy ran aground, 2=picked up by vessel, 3=stop transmitting, 4=sporadic transmissions, 5=bad batteries, 6=inactive status)";
    Int32 missing_value -999;
  }
  location_type {
    String long_name "Location Type - GPS or Argos";
  }
  DeployingShip {
    String long_name "Deploying Ship";
  }
  DeploymentStatus {
    String long_name "Status of Deployment";
  }
  BuoyTypeManufacturer {
    String long_name "Buoy Type Manufacturer";
  }
  BuoyTypeSensorArray {
    String long_name "Buoy Type Sensor Array";
  }
  PurchaserFunding {
    String long_name "Purchaser Funding";
  }
  SensorUpgrade {
    String long_name "Sensor Upgrade";
  }
  Transmissions {
    String long_name "Transmissions";
  }
  DeployingCountry {
    String long_name "Deploying Country";
  }
  DeploymentComments {
    String long_name "Deployment Comments";
  }
  ManufactureYear {
    String long_name "Manufacture Year";
  }
  ManufactureMonth {
    String long_name "Manufacture Month";
  }
  FloatDiameter {
    String long_name "Float Diameter";
  }
  SubsfcFloatPresence {
    String long_name "Subsfc Float Presence";
  }
  DrogueType {
    String long_name "Drogue Type";
  }
  DrogueLength {
    String long_name "Drogue Length";
  }
  DrogueBallast {
    String long_name "Drogue Ballast";
  }
  DragAreaAboveDrogue {
    String long_name "Drag Area Above Drogue";
  }
  DragAreaOfDrogue {
    String long_name "Drag Area Of Drogue";
  }
  DragAreaRatio {
    String long_name "Drag Area Ratio";
  }
  DrogueCenterDepth {
    String long_name "Drogue Center Depth";
  }
  DrogueDetectSensor {
    String long_name "Drogue Detect Sensor";
  }
 }
  NC_GLOBAL {
    String acknowledgement "Elipot, Shane; Sykulski, Adam; Lumpkin, Rick; Centurioni, Luca; Pazos, Mayra (2022). Hourly location, current velocity, and temperature collected from Global Drifter Program drifters world-wide. Version v2.01. NOAA National Centers for Environmental Information. Dataset. https://doi.org/10.25921/x46c-3620. Accessed [date].";
    String cdm_data_type "Trajectory";
    String cdm_trajectory_variables "ID";
    String comment "Global Drifter Program hourly data";
    String contributor_name "NOAA Global Drifter Program";
    String contributor_role "Data Acquisition Center";
    String Conventions "CF-1.6, ACDD-1.3, COARDS";
    String creator_email "aoml.dftr@noaa.gov";
    String creator_name "GDP drifter DAC";
    String creator_type "institution";
    String creator_url "https://www.aoml.noaa.gov/phod/gdp";
    String CurrentProgram "1844";
    String date_created "2023-08-31T11:08:41Z";
    String date_issued "2021-01-22T01:01:03Z";
    String date_modified "2021-01-22T01:01:03Z";
    String doi "10.25921/x46c-3620";
    Float64 Easternmost_Easting 180.0;
    String featureType "Trajectory";
    Float64 geospatial_lat_max 89.98403;
    Float64 geospatial_lat_min -78.30718;
    String geospatial_lat_resolution "tbd";
    String geospatial_lat_units "degrees_north";
    Float64 geospatial_lon_max 180.0;
    Float64 geospatial_lon_min -180.0;
    String geospatial_lon_resolution "tbd";
    String geospatial_lon_units "degrees_east";
    String history "Version v2.01.  Metadata from dirall.dat and deplog.dat
2026-10-17T21:11:25Z (local files)
2026-10-17T21:11:25Z https://erddap.aoml.noaa.gov/gdp/erddap/tabledap/drifter_hourly_qc.das";
    String infoUrl "https://www.aoml.noaa.gov/phod/dac/dirall.html";
    String institution "NOAA Atlantic Oceanographic and Meteorological Laboratory";
    String interpolation_method "Weighted Maximum Likelihood Estimator";
    String keywords "aground, alive, atlantic, attached, bad, batteries, beginning, between, buoy, circulation, collection, confidence, currents, data, date, death, deploy_date, deploy_lat, deploy_lon, deployment, drifter, drifting, drogue, drogue_lost_date, earth, Earth Science > Oceans > Ocean Circulation > Ocean Currents, eastward, end, end_date, end_lat, end_lon, err_lat, err_lon, err_sst, err_sst1, err_sst2, err_ve, err_vn, experiment, expno, fix, flg_sst, flg_sst1, flg_sst2, gap, global, hour, hourly, identification, inactive, interpolated, interval, laboratory, latitude, lon360, longitude, loss, meteorological, missing, next, noaa, northward, number, obs, observations, ocean, oceanographic, oceans, organisation, organization, percent, picked, previous, program, ran, science, sea, seawater, see, sporadic, status, still, stop, surface, surface current, surface_eastward_sea_water_velocity, surface_northward_sea_water_velocity, time, trajectory, transmissions, transmitting, type, typebuoy, typedeath, uncertain, value, velocity, vessel, water, WMO, world";
    String keywords_vocabulary "GCMD Science Keywords";
    String licence "freely available";
    String license "Creative Commons Attribution 4.0 (https://creativecommons.org/licenses/by/4.0/) This study used data collected and made freely available by the NOAA Global Drifter Program (https://www.aoml.noaa.gov/phod/gdp/) accessed from https://erddap.aoml.noaa.gov/gdp/erddap/index.html";
    String ManufactureSensorType "SVPBD";
    String ManufactureVoltage "84 volts";
    String metadata_link "https://www.aoml.noaa.gov/phod/dac/dirall.html";
    Float64 Northernmost_Northing 89.98403;
    String processing_level "Level 2 QC by GDP drifter DAC";
    String publisher_email "aoml.dftr@noaa.gov";
    String publisher_name "GDP Drifter DAC";
    String publisher_type "institution";
    String publisher_url "https://www.aoml.noaa.gov/phod/gdp";
    String source "source description";
    String sourceUrl "(local files)";
    Float64 Southernmost_Northing -78.30718;
    String standard_name_vocabulary "CF Standard Name Table v30";
    String subsetVariables "ID, location_type, WMO, expno, typedeath, typebuoy,SensorUpgrade,BuoyTypeManufacturer,BuoyTypeSensorArray,FloatDiameter,PurchaserFunding,Transmissions,DeployingCountry,ManufactureYear,ManufactureMonth,DrogueLength,DrogueBallast,DrogueDetectSensor, DeploymentStatus, DeployingShip";
    String summary "Global Drifter Program hourly drifting buoy collection. Quality control interpolated (interpolation via mathematical model fitting) data. Hourly Drifter data product exists from early 2000's to present, well suited for observing smaller-scale oceanic processes. NOAA-Atlantic Oceanographic & Meteorological Laboratory (AOML) data from a local source. The hourly QC dataset is updated on a quarterly basis, i.e. every 3 months, in delayed mode, but the data processing team has experienced unforeseen setbacks. The GDP is working as quickly as possible to update the dataset. Please reference the acknowledgment attribute to cite the dataset's DOI.";
    String time_coverage_end "2022-10-31T00:00:00Z";
    String time_coverage_start "1987-10-02T13:00:00Z";
    String title "Global Drifter Program - 1 Hour Interpolated QC Drifter Data";
    Float64 Westernmost_Easting -180.0;
  }
}
