if (!this.seantis) this.seantis = {};

seantis.locale = function(text) {
    var locale = seantis.locale;

    var lang = locale.language();
    if (typeof locale.dictionary[text] === 'undefined') {
        console.log(text + ' is untranslated');
        return text;
    }

    var ix = locale.ix(lang);
    if (ix < 0) {
        console.log('language ' + lang + ' is not supported');
        return text;
    }

    return locale.dictionary[text][ix];
};

seantis.locale._language = null;
seantis.locale.language = function() {
    var locale = seantis.locale;

    if (locale._language !== null) {
        return locale._language;
    }

    var lang = $('html').attr('lang') || $('body').attr('lang');
    if (!lang) {
        if (typeof(seantis_reservation_variables.language) != 'undefined') {
            lang = seantis_reservation_variables.language;
        } else {
            lang = 'en';
        }
    }

    locale._language = lang.split('-')[0];

    return locale._language;
};

seantis.locale.ix = function(language) {
    switch (language) {
        case 'en':
            return 0;
        case 'de':
            return 1;
        default:
            return -1;
    }
};

seantis.locale.fullcalendar = function() {
    if (seantis.locale.language() == 'de') {
        return {
            buttonText: {
                today: 'Heute',
                month: 'Monat',
                day: 'Tag',
                week: 'Woche'
            },
            monthNames: ['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'],
            monthNamesShort: ['Jan','Feb','Mär','Apr','Mai','Jun','Jul','Aug','Sept','Okt','Nov','Dez'],
            dayNames: ['Sonntag','Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag'],
            dayNamesShort: ['So','Mo','Di','Mi','Do','Fr','Sa']
        };
    }

    return {};
};

seantis.locale.translate = function(html) {
    return html.replace(/%([a-zA-Z0-9 ]+)%/g, function(text, group) {
        return seantis.locale(group);
    });
};

seantis.locale.dictionary = {
    'free' : [
        'Free',
        'Frei'
    ],
    'continue' : [
        'Continue',
        'Weiter'
    ],
    'reserve' : [
        'Reserve',
        'Reservieren'
    ]
};
