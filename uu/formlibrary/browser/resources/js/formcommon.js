/*jshint browser: true, nomen: false, eqnull: true, es5:true, trailing:true */

(function ($) {

    "use strict";

    $(document).ready(function(){
        var viewname = $('meta[name=VIEWNAME]').attr('content');
        if (viewname == 'edit') {
            /* hide portlet columns via deco.gs class removal */
            $('#portal-column-content').removeClass('position-1:4');
            $('#portal-column-content').removeClass('width-3:4');
            $('#portal-column-two').removeClass('position-3:4');
            $('#portal-column-two').removeClass('width-1:4');
            /* change deco.gs classes for main column to full-width */
            $('#portal-column-content').addClass('position-0');
            $('#portal-column-content').addClass('width-full');
            }
        $('a.meta-toggle').click(function() {
            var clicklink = $(this);
            if (clicklink.text() == '[HIDE metadata and instructions.]') {
                clicklink.text('[SHOW metadata and instructions.]');
            }
            else {
                clicklink.text('[HIDE metadata and instructions.]');
            }
            clicklink.parents('div.form-meta').children('div.wrapper').slideToggle();
            });
    });

}(jQuery));

