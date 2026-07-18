// ============================================================================
// 03_ndvi_ndbi.js
// Week 1-2 — spectral indices from the Landsat 8/9 dry-season composite.
//
// What this does:
//   1. Rebuilds the same cloud-masked dry-season median composite as
//      01_composite.js (kept in sync manually — see the note in that file).
//   2. NDVI = (NIR - RED) / (NIR + RED)  = normalizedDifference(SR_B5, SR_B4)
//   3. NDBI = (SWIR1 - NIR) / (SWIR1 + NIR) = normalizedDifference(SR_B6, SR_B5)
//   4. Exports colombo_ndvi_2024_dry_season.tif and colombo_ndbi_2024_dry_season.tif
//      to Google Drive, at 30 m in EPSG:4326 (matches src/check_raw_data.py,
//      which expects both indices within [-1, 1] and CRS EPSG:4326).
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

var ndvi = composite.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI').clip(AOI);
var ndbi = composite.normalizedDifference(['SR_B6', 'SR_B5']).rename('NDBI').clip(AOI);

print('NDVI stats', ndvi.reduceRegion({
  reducer: ee.Reducer.minMax().combine({reducer2: ee.Reducer.mean(), sharedInputs: true}),
  geometry: AOI, scale: 30, maxPixels: 1e9
}));
print('NDBI stats', ndbi.reduceRegion({
  reducer: ee.Reducer.minMax().combine({reducer2: ee.Reducer.mean(), sharedInputs: true}),
  geometry: AOI, scale: 30, maxPixels: 1e9
}));

Map.centerObject(AOI, 12);
Map.addLayer(ndvi, {min: -0.2, max: 0.8, palette: ['brown', 'white', 'green']}, 'NDVI');
Map.addLayer(ndbi, {min: -0.5, max: 0.5, palette: ['blue', 'white', 'red']}, 'NDBI');

Export.image.toDrive({
  image: ndvi,
  description: 'colombo_ndvi_2024_dry_season',
  folder: 'colombo_uhi_raw',
  fileNamePrefix: 'colombo_ndvi_2024_dry_season',
  region: AOI,
  scale: 30,
  crs: 'EPSG:4326',
  maxPixels: 1e9,
  fileFormat: 'GeoTIFF'
});

Export.image.toDrive({
  image: ndbi,
  description: 'colombo_ndbi_2024_dry_season',
  folder: 'colombo_uhi_raw',
  fileNamePrefix: 'colombo_ndbi_2024_dry_season',
  region: AOI,
  scale: 30,
  crs: 'EPSG:4326',
  maxPixels: 1e9,
  fileFormat: 'GeoTIFF'
});
