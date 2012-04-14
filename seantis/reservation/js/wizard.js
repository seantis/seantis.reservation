if (!this.seantis) this.seantis = {};
if (!this.seantis.wizard) this.seantis.wizard = {};

(function($) {
    seantis.wizard.init = function() {
        var form = $('form.seantis-reservation-form');
        if (form.length === 0)
            return;

        if (form.length === 0) {
            return;
        }

        form.find('.formTabs').addClass('wizardSteps');

        var tabs = form.find('.formTab');
        if (tabs.length === 0) {
            return;
        }

        tabs.click(function() {
            $(this).addClass('visited');
        });

        $(tabs[0]).addClass('visited');


    };
})(jQuery);