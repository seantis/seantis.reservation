if (!this.seantis) this.seantis = {};
if (!this.seantis.search) {
    this.seantis.search = {};
}

seantis.search.init_select_buttons = function() {
    var available_checkboxes = $(
        '.searchresults input[type="checkbox"]:not([disabled])'
    );

    $('#select-all-searchresults').click(function() {
        available_checkboxes.prop('checked', true);
        seantis.search.adjust_button_state_to_selection();
    });
    $('#select-no-searchresults').click(function() {
        available_checkboxes.prop('checked', false);
        seantis.search.adjust_button_state_to_selection();
    });
    available_checkboxes.change(function() {
        seantis.search.adjust_button_state_to_selection();
    });
};

seantis.search.adjust_button_state_to_selection = function() {
    var submit_button = $('#reserve-selection-form input[type="submit"]');

    if ($('.searchresults input[type="checkbox"]').is(':checked')) {
        submit_button.prop('disabled', false);
    } else {
        submit_button.prop('disabled', true);
    }
};

seantis.search.init_overlays = function() {
    var submit = $('.searchresults input[type="submit"]');
    if (submit.length >= 0) seantis.search.init_submit(submit);
};

seantis.search.init_submit = function(submit) {
    "use strict"; // <- hah!

    /*
        WARNING, FACEPALM INDUCING CODE UP AHEAD!

        The reservation search results need to be shown in a reservation form,
        displayed in an overlay. Unfortunately, plone.app.jquerytools only
        supports GET forms.

        More unfortunately, GET forms cannot be used here because the
        parameter-list could become quite long in certain cases. Which of
        course is no problem because everyone accepts *really* long urls...

        ...everyone except for IE. Including new versions.

        So we need to use POST. And a hack for plone.app.jquerytools.

        What's done is this:

        1. When submit is clicked, an AJAX post request is sent to the server.
        2. The result is kept and fed into the overlay.
        3. The overlay does not like to be fed, so we force-fed.
        4. The overlay really resists this even more, so we pretty much
           act like Aliens and treat the overlay like Eric Cartman.

        Please remain calm when you have to fix this code, which will
        inevitably break. My deadline was probably more important than
        yours anyway?

    */
    var loading = false;

    submit.click(function(e) {
        $.post('./reserve-selection', $('#reserve-selection-form').serialize(),
            function(data, status, xhr) {

                // Create a link outside the DOM and point to an address
                // which is public, but doesn't ask too much from the server.
                // (@uuid returns only a few bytes)
                var link = $('<a href="./@@uuid"></a>');

                // Keep the return of the POST request around for the overlay
                var content = $(data).find('#content > *');

                reservation_overlay_init(link, {
                    config: {
                        onBeforeLoad: function() {

                            // We'll call onBeforeLoad later which will
                            // naturally lead to an endless loop if we don't
                            // stop here.
                            if (loading === true) {
                                return;
                            } else {
                                loading = true;
                            }

                            var overlay = this.getOverlay();
                            var inner_el = overlay.find('.pb-ajax');

                            // Reach into the guts of plone.app.jquerytools's
                            // overlayhelper and extract the code that
                            // sets up the overlay proper.
                            var postprocessor = inner_el[0].handle_load_inside_overlay;

                            // Cram our own html into the overlay
                            inner_el.html(content);

                            // Setup the overlay by an means necessary
                            postprocessor.call(
                                overlay.find('.pb-ajax'), content.html()
                            );

                            // Call the before load function, which is this
                            // function we're in, but which also does some
                            // stuff defined elsewhere, which we need
                            // to run (like setting up the form wizard)
                            if (this.getConf().onBeforeLoad) {
                                this.getConf().onBeforeLoad.call(this);
                            }

                            loading = false;
                        }
                    }
                });

                // Run the crime against humanity found in the lines above.
                link.click();
            }
        );

        // Let the browser know that we really meant it and don't care
        // about the user clicking submit tons of times.
        submit.removeClass('submitting');
        e.preventDefault();
    });
};

(function($) {
    $(document).ready(function() {
        seantis.search.init_overlays();
        seantis.search.init_select_buttons();
    });
})(jQuery);