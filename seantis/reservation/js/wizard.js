if (!this.seantis) this.seantis = {};
if (!this.seantis.wizard) this.seantis.wizard = {};

(function($) {
    seantis.wizard.init = function() {

        /* on seantis reservation forms */
        var form = $('form.seantis-reservation-form');
        if (form.length === 0) {
            return;
        }

        form.find('.formTabs').addClass('wizardSteps');

        var enable_next_next = form.hasClass('next-next-wizard');

        /* if there is more than a single tab */
        var tabs = form.find('.formTab');
        if (tabs.length <= 1) {
            return;
        }

        for (var i=0; i< tabs.length; i++) {
            $(tabs[i]).data('wizard-step', i);
        }

        var submit = form.find('input.context');
        var current_tab = $(tabs[0]);
        current_tab.click();

        /* highlight visited tabs */
        tabs.find('a').click(function() {
            current_tab = $(this).parent();
            $(tabs).removeClass('selected');
            current_tab.addClass('selected');
            current_tab.addClass('visited');

            if (enable_next_next) {
                if (current_tab.hasClass('lastFormTab')) {
                    submit.val(seantis.locale('reserve'));
                } else {
                    submit.val(seantis.locale('continue'));
                }
            }
        });

        /* and submit on the last tab only, showing next->next until then*/
        if (enable_next_next) {
            submit.click(function(e) {
                if (current_tab.hasClass('lastFormTab')) {
                    return; // do submit
                }

                var nextstep = current_tab.data('wizard-step') + 1;
                $(tabs[nextstep]).find('a').click();

                e.preventDefault();
            });
        }

        /* ensure correct classes on (re)load */
        $(tabs).removeClass('visited');
        $(tabs).find('a').removeClass('selected');
        $(tabs[0]).addClass('selected visited');

        if (enable_next_next) {
            submit.val(seantis.locale('continue'));
        }

        /* after ajax reloading the first tab is sometimes unselected */
        current_tab.find('a').click();
    };
})(jQuery);