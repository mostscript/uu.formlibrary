
$(document).ready(function () {
    module('Criteria editor tests.');
    test( "tests run", function () {
        ok( 1 == "1", 'QUnit loads, runs,');
    });
    // TODO: mock ajax json for fields
    // TODO: mock comparators-by-field ajax json
    // TODO: OrderedMapping tests
    // TODO: FieldQuery tests
    // TODO: CriteriaForm tests
    // TODO: CriteriaForms container / view tests
    // TODO: form CRUD integration tests:
    //          * Add 1,2 rows/queries via UI event trigger
    //          * Add programmatically
    //          * Remove query/row via UI event trigger
    //          * Remove programmatically
    //          * Update field, set to valid option
    //          * Update field, set to null
    //          * Update field, set to dupe, expect alert/exception?
    //          * Update comparator, set to valid
    //          * Update comparator, set to null
    //          * Update comparator, expect proper value widget, vocab
    //          * Change form operator AND/OR, rows labeled properly
    //          * Change form operator AND/OR, payload updated
    //          * Load from payload (saved data) mock(s), test result
});

