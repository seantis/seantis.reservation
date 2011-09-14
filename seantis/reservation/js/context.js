if (!this.seantis) this.seantis = {};

// Adds the contextmenu to the element and adds plone overlays to all
// links in the content
seantis.contextmenu = function(element, content) {
    element.miniTip({
        title: '',
        content: content,
        anchor: 'e',
        event: 'hover',
        aHide: false,
        fadeIn: 100,
        render: function(element) {
            seantis.calendar.form_overlay($('a', element));
        }
    });  
};