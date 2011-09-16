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
        locale._languge = 'en';
    } else {
        locale._language = lang;
    }    
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

seantis.locale.translate = function(html) {
    return html.replace(/%([a-zA-Z0-9 ]+)%/g, function(text, group) {
        return seantis.locale(group);
    });
};

seantis.locale.dictionary = {
    'reserve' : [
        'Reserve',
        'Reservieren'
    ],
    'free' : [
        'Free',
        'Frei'
    ],
    'edit' : [
        'Edit',
        'Bearbeiten'
    ]
};
