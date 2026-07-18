// ============================================================================
// 02_lst.js
// Week 1 — Land Surface Temperature from the Landsat 8/9 dry-season composite.
//
// What this does:
//   1. Rebuilds the same cloud-masked dry-season median composite as
//      01_composite.js (kept in sync manually — see the note in that file).
//   2. Takes the thermal band (ST_B10, already scaled to Kelvin by the
//      Collection 2 scale factors applied in buildComposite()).
//   3. Converts Kelvin -> Celsius.
//   4. Exports colombo_lst_2024_dry_season.tif to Google Drive, at Landsat's
//      native 30 m, reprojected to EPSG:4326 (matches the raw-data audit in
//      src/check_raw_data.py, which expects LST in plausible Celsius range
//      20-55 and CRS EPSG:4326 — final alignment to the EPSG:32644 / 100 m
//      analysis grid happens later in src/preprocess.py).
// ============================================================================

// ---------------------------------------------------------------------------
// SHARED SETUP — identical to 01_composite.js. Keep in sync if you edit either.
// ---------------------------------------------------------------------------

var AOI = ee.Geometry.Rectangle([79.8189, 6.8618, 79.8910, 6.9821], 'EPSG:4326', false);

var DATE_FILTER = ee.Filter.or(
  ee.Filter.date('2023-01-01', '2023-03-31'),
  ee.Filter.date('2024-01-01', '2024-03-31')
);

var CLOUD_COVER_MAX = 50;

function maskAndScaleL8L9(image) {
  var qa = image.select('QA_PIXEL');
  var dilatedCloud = 1 << 1;
  var cirrus = 1 << 2;
  var cloud = 1 << 3;
  var cloudShadow = 1 << 4;

  var mask = qa.bitwiseAnd(dilatedCloud).eq(0)
    .and(qa.bitwiseAnd(cirrus).eq(0))
    .and(qa.bitwiseAnd(cloud).eq(0))
    .and(qa.bitwiseAnd(cloudShadow).eq(0));

  var opticalBands = image.select('SR_B.').multiply(0.0000275).add(-0.2);
  var thermalBands = image.select('ST_B.*').multiply(0.00341802).add(149.0);

  return image.addBands(opticalBands, null, true)
    .addBands(thermalBands, null, true)
    .updateMask(mask);
}

function buildComposite() {
  var l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
    .filterBounds(AOI)
    .filter(DATE_FILTER)
    .filter(ee.Filter.lt('CLOUD_COVER', CLOUD_COVER_MAX));

  var l9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')
    .filterBounds(AOI)
    .filter(DATE_FILTER)
    .filter(ee.Filter.lt('CLOUD_COVER', CLOUD_COVER_MAX));

  var merged = l8.merge(l9).map(maskAndScaleL8L9);

  return merged.median().clip(AOI);
}

// ---------------------------------------------------------------------------
// SCRIPT BODY
// ---------------------------------------------------------------------------

var composite = buildComposite();

var lstCelsius = composite.select('ST_B10')
  .subtract(273.15)
  .rename('LST_Celsius')
  .clip(AOI);

print('LST stats (dry-season, Celsius)', lstCelsius.reduceRegion({
  reducer: ee.Reducer.minMax().combine({reducer2: ee.Reducer.mean(), sharedInputs: true}),
  geometry: AOI,
  scale: 30,
  maxPixels: 1e9
}));

Map.centerObject(AOI, 12);
Map.addLayer(lstCelsius, {min: 25, max: 40, palette: ['blue', 'yellow', 'red']}, 'LST (Celsius)');

Export.image.toDrive({
  image: lstCelsius,
  description: 'colombo_lst_2024_dry_season',
  folder: 'colombo_uhi_raw',
  fileNamePrefix: 'colombo_lst_2024_dry_season',
  region: AOI,
  scale: 30,
  crs: 'EPSG:4326',
  maxPixels: 1e9,
  fileFormat: 'GeoTIFF'
});
