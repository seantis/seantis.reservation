var reservation_overlay_init = null;

(function($) {

    var popups = null;

    // Shows portalMessages swallowed by the prepOverlay mechanism
    // on the parent page
    var get_popup_messages = function(soup) {
        // all portal messages are in the same DOM (no iframe), so get the first
        var target = $('dl.portalMessage:first');
        var messages = soup.find('dl.portalMessage');

        // filter out the ones without any text
        messages = _.filter(messages, function(m) {
            return !_.isEmpty($.trim($(m).find('dd').text()));
        });

        if (!messages.length) {
            return {};
        }

        messages = $(messages);

        var show = function() {
            messages.hide();
            target.after(messages);
            messages.fadeIn('slow');
        };
        var hide = function() {
            messages.fadeOut('slow');
            popups = null;
        };

        return {show:show, hide:hide};
    };

    // call with the result of get_popup_messages to show / hide
    var show_popup_messages = function(get_result) {
        if (!get_result) {
            return;
        }

        setTimeout(get_result.show, 0);
        setTimeout(get_result.hide, 4000);
    };

    var disable_readonly_calendars = function() {
        _.defer(function() {
            $('input[readonly]').siblings('.caltrigger').hide();
        });
    };

    var init_tinymce = function() {
        $('.richtext-field textarea').each(function(index, el) {
            // force tinymce to init again
            var id = $(el).attr('id');
            delete InitializedTinyMCEInstances[id];
            
            var cfg = new TinyMCEConfig(id);
            cfg.init();

        });
    };

    var on_formload_success = function(e, parent, form) {
        if ($.fn.ploneTabInit) {
            parent.ploneTabInit();
        }
        seantis.formgroups.init();
        seantis.wizard.init();

        disable_readonly_calendars();
        init_tinymce();
    };

    var on_formload_failure = function(e, parent, form) {
        if (popups) {
            show_popup_messages(popups);
        }
    };

    reservation_overlay_init = function(elements, options) {
        // bind events (ensuring that there's only one handler at a time)
        // -> because there can only be one overlay at any given time
        (function(formload_success, formload_failure) {
            $(document).unbind('seantis.formload_success');
            $(document).unbind('seantis.formload_failure');

            $(document).bind('seantis.formload_success', formload_success);
            $(document).bind('seantis.formload_failure', formload_failure);
        })(on_formload_success, on_formload_failure);

        var before_load = function() {
            seantis.formgroups.init();
            seantis.wizard.init();
            disable_readonly_calendars();
            init_tinymce();
            jQuery = $;
        };

        var after_post = function(el) {
            seantis.formgroups.init(el);
            seantis.your_reservations.update();
            popups = get_popup_messages(el);
            $(document).trigger('reservations-changed');

            // z3cform renders views with widget-only errors
            // with an empty field.error div
            // it makes the forms have too much white space, so
            // remove it here
            el.find('div.field.error').each(function(ix, _field) {
                var field = $(_field);
                if (field.children().length === 0) {
                    field.remove();
                }
            });
        };

        var default_options = {
            subtype:          'ajax',
            filter:           common_content_filter,
            formselector:     'form.seantis-reservation-form',
            closeselector:    '[name=form.buttons.cancel]',
            noform:           'close',
            afterpost:        (function() {}),
            config: {
                onBeforeLoad: (function() {}),
                onClose: (function() {})
            }
        };

        var all_options = _.defaults(options, default_options);
        all_options.config = _.defaults(options.config, default_options.config);

        var _after_post = all_options.afterpost;
        all_options.afterpost = function(el) {
            after_post.apply(this, arguments);
            _after_post.apply(this, arguments);
        };

        var _before_load = all_options.config.onBeforeLoad;
        all_options.config.onBeforeLoad = function() {
            before_load.apply(this, arguments);
            _before_load.apply(this, arguments);
        };

        elements.prepOverlay(all_options);
    };

    var _eval_stripped = function(responseText) {
        // the overlay helper script of plone.app.jquerytools strips
        // script tags from the forms which results in calendar widgets
        // not showing up

        // this function tries to compensate for that by parsing the
        // plain html code for those tags and executing them using eval

        // this is horribly hackish and somewhat insecure (if the user
        // is able to add his own script tags to a document, which he shouldn't)

        // I must confess though that it was way more fun to write than it should
        // have been...

        // only do it on whitelisted forms

        var whitelist = [
            /kssattr-formname-allocate/gi,
            /kssattr-formname-@@edit/gi,
            /kssattr-formname-reserve/gi
        ];

        var whitelisted = _.find(whitelist, function(expr) {
            return expr.test(responseText);
        });

        if (!whitelisted) return;

        var re = /<script type="text\/javascript">([\s\S]*?)<\/script>/gi;
        var matches = null;

        // eval all scripts (index 0 is the whole tag, index 1 is what's within)
        while ((matches = re.exec(responseText)) !== null) {
            try {
                eval(matches[1]);
            } catch (e) {}
        }
    };

    $(document).ready(function() {
        $(document).bind('formOverlayLoadSuccess', function(e, overlay, form, api, pb, ajax_parent) {
            $(document).trigger('seantis.formload_success', [ajax_parent, form]);
        });
        $(document).bind('formOverlayLoadFailure', function(e, overlay, form, api, pb, ajax_parent) {
            $(document).trigger('seantis.formload_failure', [ajax_parent, form]);
        });
        $(document).bind('loadInsideOverlay', function(e, el, responseText, errorText, api) {
            _.defer(function() {
                _eval_stripped(responseText);
            });
        });
        $(document).bind('formOverlayStart', function(e, overlay, responseText, statusText, xhr, form) {
            _.defer(function() {
                _eval_stripped(responseText);
            });
        });
    });

})(jQuery);