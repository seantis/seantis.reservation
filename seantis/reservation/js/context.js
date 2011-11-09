if (!this.seantis) this.seantis = {};

// Adds the contextmenu to the element and adds plone overlays to all
// links in the content
seantis.contextmenu = function(event, element, calendar) {
    var content = seantis.contextmenu.build(event);
    if (!content)
        return;
        
    element.miniTip({
        title: '',
        content: seantis.contextmenu.build(event),
        anchor: 'e',
        event: 'hover',
        aHide: false,
        fadeIn: 100,
        render: function(element) {
            calendar.overlay_init($('a', element));
        }
    });  
};

seantis.contextmenu.build = function(event) {
    var title = _.template('<div><%= text %></div>');
    var entry = _.template('<a class="seantis-reservation-reserve" href="<%= url %>"><%= text %></a>');
    var locale = seantis.locale;
    var html = '';

    if (event.url || event.editurl || event.removeurl) {
        var single = [
            title({text: locale('entry')}),
            event.url && entry({text: locale('reserve'), url:event.url}),
            event.editurl && entry({text: locale('edit'),    url:event.editurl}),
            event.removeurl && entry({text: locale('remove'),  url:event.removeurl})
        ];

        html = single.join('');
    }

    if (event.groupurl || event.removegroupurl) {
        var group = [
            title({text: locale('group')}),
            event.groupurl && entry({text: locale('showgroup'), url:   event.groupurl}),
            event.removegroupurl && entry({text: locale('removegroup'), url: event.removegroupurl})
        ];    

        html += group.join('');
    }

    return html;
};