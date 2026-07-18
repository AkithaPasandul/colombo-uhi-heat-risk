// ============================================================================
// 04_aux_layers.js
// Week 1-2 — auxiliary layers, each clipped to the AOI and exported to
// Google Drive -> data/raw/. These are independent datasets (no Landsat
// composite dependency), so this script is fully standalone.
//
// Layers:
//   - ESA WorldCover v200 (2021)           -> colombo_worldcover_2021.tif
//   - WorldPop 100m population (2020)      -> colombo_worldpop_2020.tif
//   - SRTM elevation                       -> colombo_elevation_srtm.tif
//   - GHS-BUILT-S (2020 epoch)             -> colombo_ghsl_built_2020.tif
//   - MODIS MOD11A2 day+night LST          -> colombo_modis_lst_2024_dry_season.tif
//
// CRS/scale notes (matches src/check_raw_data.py, the raw-data audit gate):
//   - WorldCover, WorldPop, SRTM and MODIS are exported in EPSG:4326.
//   - GHS-BUILT-S is exported in its NATIVE CRS (ESRI:54009 / Mollweide) —
//     do not reproject it here, the audit explicitly checks for Mollweide.
//   - Final alignment of all layers to the EPSG:32644 / 100 m analysis grid
//     happens later in src/preprocess.py, not here.
// ============================================================================

// AOI: Colombo bounding box — mirrors config/config.yaml and 01_composite.js.
var AOI = ee.Geometry.Rectangle([79.8189, 6.8618, 79.8910, 6.9821], 'EPSG:4326', false);

var EXPORT_FOLDER = 'colombo_uhi_raw';

// ---------------------------------------------------------------------------
// ESA WorldCover v200 (2021) — land use / land cover, 10 m native.
// ---------------------------------------------------------------------------
var worldcover = ee.ImageCollection('ESA/WorldCover/v200').first()
  .select('Map')
  .clip(AOI);

Export.image.toDrive({
  image: worldcover,
  description: 'colombo_worldcover_2021',
  folder: EXPORT_FOLDER,
  fileNamePrefix: 'colombo_worldcover_2021',
  region: AOI,
  scale: 10,
  crs: 'EPSG:4326',
  maxPixels: 1e9,
  fileFormat: 'GeoTIFF'
});

// ---------------------------------------------------------------------------
// WorldPop 100 m population density (Sri Lanka, 2020, unconstrained).
// ---------------------------------------------------------------------------
var worldpop = ee.ImageCollection('WorldPop/GP/100m/pop')
  .filter(ee.Filter.eq('country', 'LKA'))
  .filter(ee.Filter.eq('year', 2020))
  .mosaic()
  .clip(AOI);

Export.image.toDrive({
  image: worldpop,
  description: 'colombo_worldpop_2020',
  folder: EXPORT_FOLDER,
  fileNamePrefix: 'colombo_worldpop_2020',
  region: AOI,
  scale: 100,
  crs: 'EPSG:4326',
  maxPixels: 1e9,
  fileFormat: 'GeoTIFF'
});

// ---------------------------------------------------------------------------
// SRTM elevation, 30 m — used for slope/terrain context.
// ---------------------------------------------------------------------------
var elevation = ee.Image('USGS/SRTMGL1_003').select('elevation').clip(AOI);

Export.image.toDrive({
  image: elevation,
  description: 'colombo_elevation_srtm',
  folder: EXPORT_FOLDER,
  fileNamePrefix: 'colombo_elevation_srtm',
  region: AOI,
  scale: 30,
  crs: 'EPSG:4326',
  maxPixels: 1e9,
  fileFormat: 'GeoTIFF'
});

// ---------------------------------------------------------------------------
// GHS-BUILT-S (built-up surface), 2020 epoch, 10 m, native Mollweide CRS.
// Kept in Mollweide on purpose — see CRS note above.
// ---------------------------------------------------------------------------
var ghslBuilt = ee.ImageCollection('JRC/GHSL/P2023A/GHS_BUILT_S')
  .filter(ee.Filter.date('2020-01-01', '2021-01-01'))
  .first()
  .select('built_surface')
  .clip(AOI);

Export.image.toDrive({
  image: ghslBuilt,
  description: 'colombo_ghsl_built_2020',
  folder: EXPORT_FOLDER,
  fileNamePrefix: 'colombo_ghsl_built_2020',
  region: AOI,
  scale: 10,
  // no crs override -> keeps the asset's native ESRI:54009 (Mollweide)
  maxPixels: 1e9,
  fileFormat: 'GeoTIFF'
});

// ---------------------------------------------------------------------------
// MODIS MOD11A2 — 8-day day + night LST composite, dry season 2023 & 2024,
// used as an independent validation / robustness check against the Landsat
// LST in 02_lst.js (coarser 1 km resolution, different sensor/overpass time).
// ---------------------------------------------------------------------------
var modisDateFilter = ee.Filter.or(
  ee.Filter.date('2023-01-01', '2023-03-31'),
  ee.Filter.date('2024-01-01', '2024-03-31')
);

var modisLst = ee.ImageCollection('MODIS/061/MOD11A2')
  .filterBounds(AOI)
  .filter(modisDateFilter)
  .select(['LST_Day_1km', 'LST_Night_1km'])
  .map(function (image) {
    // Scale factor 0.02 -> Kelvin, then convert to Celsius.
    return image.multiply(0.02).subtract(273.15)
      .copyProperties(image, ['system:time_start']);
  })
  .mean()
  .rename(['LST_Day_Celsius', 'LST_Night_Celsius'])
  .clip(AOI);

Export.image.toDrive({
  image: modisLst,
  description: 'colombo_modis_lst_2024_dry_season',
  folder: EXPORT_FOLDER,
  fileNamePrefix: 'colombo_modis_lst_2024_dry_season',
  region: AOI,
  scale: 1000,
  crs: 'EPSG:4326',
  maxPixels: 1e9,
  fileFormat: 'GeoTIFF'
});

// ---------------------------------------------------------------------------
// Quick visual sanity check for all layers.
// ---------------------------------------------------------------------------
Map.centerObject(AOI, 12);
Map.addLayer(worldcover, {}, 'ESA WorldCover 2021', false);
Map.addLayer(worldpop, {min: 0, max: 500, palette: ['white', 'orange', 'red']}, 'WorldPop 2020', false);
Map.addLayer(elevation, {min: 0, max: 100, palette: ['green', 'yellow', 'brown']}, 'SRTM elevation', false);
Map.addLayer(ghslBuilt, {min: 0, max: 100, palette: ['white', 'grey', 'black']}, 'GHS-BUILT-S 2020', false);
Map.addLayer(modisLst.select('LST_Day_Celsius'), {min: 25, max: 40, palette: ['blue', 'yellow', 'red']},
  'MODIS day LST', false);
