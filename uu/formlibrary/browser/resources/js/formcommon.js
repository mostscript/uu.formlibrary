/*jshint browser: true, nomen: false, eqnull: true, es5:true, trailing:true */

(function ($) {

    "use strict";

    var msgShow = '[SHOW metadata and instructions.]',
        msgHide = '[HIDE metadata and instructions.]';

    function hookupMetaToggle() {
        var viewname = $('#formcore').attr('data-viewname'),
            colContent = $('#portal-column-content'),
            colTwo = $('#portal-column-two'),
            toggle = $('a.meta-toggle');
        if (viewname === 'edit') {
            /* hide portlet columns, main column to full width via deco.gs
             * class names modification of defaults 
             */
            colContent
                .removeClass('position-1:4 width-3:4')
                .addClass('position-0 width-full');
            colTwo.removeClass('position-3:4 width-1:4');
        }
        toggle.click(
            function () {
                var link = $(this),
                    hidden = link.text() === msgHide,
                    wrapper = link.parents('.form-meta').children('.wrapper');
                link.text((hidden) ? msgShow : msgHide);
                wrapper.slideToggle();
            }
        );
    }

    function disableInlineValidation() {
        // remove all z3cformInlineValidation classes everywhere
        $('.z3cformInlineValidation').removeClass('z3cformInlineValidation');
    }

    $(document).ready(function(){
        hookupMetaToggle();
        disableInlineValidation();
    });

}(jQuery));

