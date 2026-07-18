// ============================================================================
// 01_composite.js
// Week 1 — dry-season median surface reflectance composite (Landsat 8/9 C2 L2)
//
// What this does:
//   1. Merges Landsat 8 + Landsat 9 Collection 2 Level 2 (Surface Reflectance).
//   2. Filters to the Colombo AOI and the dry-season windows (Jan-Mar, 2023 & 2024
//      — two years so a cloudy 2024 doesn't leave gaps in the composite).
//   3. Masks cloud / cloud shadow / cirrus / dilated cloud using the QA_PIXEL band.
//   4. Applies the Collection 2 scale factors to get reflectance (0-1) and
//      brightness temperature (Kelvin).
//   5. Takes the per-pixel median -> one cloud-free composite for the AOI.
//
// This composite is the base that 02_lst.js and 03_ndvi_ndbi.js build on.
// Each of those scripts rebuilds the same composite locally (see the
// "SHARED SETUP" block below, copied verbatim across 01/02/03) so every
// script can be run standalone in the Code Editor without needing an
// Earth Engine Asset or a published require() module. If you change the
// AOI, dates, or cloud mask here, copy the change into 02 and 03 too.
//
// Run this script first to sanity-check the composite (true-colour preview,
// AOI outline, pixel count) before moving on to 02/03/04.
// ============================================================================

// ---------------------------------------------------------------------------
// SHARED SETUP — mirrors config/config.yaml. Edit both if either changes.
// ---------------------------------------------------------------------------

// AOI: Colombo bounding box (NOT an administrative boundary).
// W 79.8189, S 6.8618, E 79.8910, N 6.9821 — matches data/external/cmc_boundary.geojson.
var AOI = ee.Geometry.Rectangle([79.8189, 6.8618, 79.8910, 6.9821], 'EPSG:4326', false);

// Dry-season windows. 2024 is the target year; 2023 is added as a fallback
// so the median has enough clear observations even where 2024 is cloudy.
var DATE_FILTER = ee.Filter.or(
  ee.Filter.date('2023-01-01', '2023-03-31'),
  ee.Filter.date('2024-01-01', '2024-03-31')
);

var CLOUD_COVER_MAX = 50; // scene-level prefilter, cheap way to skip badly clouded scenes

// Cloud / shadow / cirrus / dilated-cloud mask from QA_PIXEL (Collection 2 L2 bit flags),
// plus the official per-band scale factors -> reflectance (SR) and Kelvin (ST).
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

// Builds the cloud-free dry-season median composite, clipped to the AOI.
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
// SCRIPT BODY — run this file to inspect the composite before using it in
// 02_lst.js / 03_ndvi_ndbi.js.
// ---------------------------------------------------------------------------

var composite = buildComposite();

print('Composite bands', composite.bandNames());
print('Scene count going into the median (sanity check — want > ~5)',
  ee.ImageCollection('LANDSAT/LC08/C02/T1_L2').filterBounds(AOI).filter(DATE_FILTER)
    .merge(ee.ImageCollection('LANDSAT/LC09/C02/T1_L2').filterBounds(AOI).filter(DATE_FILTER))
    .size());

Map.centerObject(AOI, 12);
Map.addLayer(AOI, {color: 'red'}, 'AOI (Colombo bbox)', true, 0.3);
Map.addLayer(composite, {bands: ['SR_B4', 'SR_B3', 'SR_B2'], min: 0, max: 0.3},
  'True colour composite (dry season median)');
