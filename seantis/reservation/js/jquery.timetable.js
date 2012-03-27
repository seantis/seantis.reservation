(function ( $, window, document, undefined ) {

    var pluginName = 'timetable',
        defaults = {
            min_hour: 0,
            max_hour: 24,
            show_text: true
        };

    function Plugin( element, options ) {
        this.element = element;

        this.options = $.extend( {}, defaults, options) ;

        this._defaults = defaults;
        this._name = pluginName;

        this.init();
    }

    Plugin.prototype.init = function () {
        this.render();
    };
    
    Plugin.prototype.parse_time = function(time) {
        var split = time.split(':');
        if (!split.length == 2) {
            console.log('unable to parse ' + time);
            return undefined;            
        }
        
        return {
            hour: parseInt(split[0], 10),          
            minute: parseInt(split[1], 10)
        };
    };
        
    // Parses the given timestrings and bounds them to the min / max hour
    Plugin.prototype.normalize_range = function(_start, _end) {
        var start = this.parse_time(_start);
        var end = this.parse_time(_end);
        
        if (start.hour < this.options.min_hour)
            start = {hour: this.options.min_hour, minute: 0};
        if (end.hour > this.options.max_hour)
            end = {hour: this.options.max_hour + 1, minute: 0};
        
        return {"start":start, "end":end};       
    };
        
    // Goes through the min / max timerange and returns an item
    // for each cell that should be drawn in the table.
        
    // Each item offers the following properties:
    //  * left   distance from start of the cell in %
    //  * right  distance from end of the cell in %
    //  * span   number of cells the item spans
    //  * state  occupied / free
    //  * text   text of the occupied cell containing the start / end time
    Plugin.prototype.merged_divisions = function(_start, _end) {
        
        var range = this.normalize_range(_start, _end);
        var start = range.start;
        var end = range.end;

        var result = new Array();
        
        for (var hour=this.options.min_hour; hour <= this.options.max_hour; hour++) {
            
            // outside of start & end are the free cells
            if (hour < start.hour || end.hour < hour) {
                result.push({left: 0, right: 0, span: 1, state:'free', text:''});
                continue;
            }
            
            // one single occupied cell
            if (hour == start.hour && hour == end.hour) {
                result.push({
                    left: (start.minute / 60) * 100,
                    right: ((60 - end.minute) / 60) * 100,
                    span: 1,
                    state: 'occupied',
                    text: _start + ' - ' + _end
                });
                continue;                
            }

            // a item which will span multiple cells
            if (hour == start.hour) {
                result.push({
                    left: (start.minute / 60) * 100,
                    right: 0,
                    span: 1,
                    state: 'occupied',
                    text: _start + ' - ' + _end
                });     
                continue;
            }
            
            var previous = result[result.length - 1];
            
            // increment span of most recent item
            if (start.hour < hour && hour < end.hour) {
                previous.span += 1;

                continue;                
            }
            
            // close last item
            if (hour == end.hour) {
                
                // if the hour ends on zero the last cell is free
                if (end.minute === 0) {                
                    result.push({
                        left: 0, right: 0, state: 'free', span: 1                        
                    });
                } else {
                    previous.right = ((60 - end.minute) / 60) * 100;
                    previous.span += 1;
                }
                
                previous.left = (previous.left / (previous.span * 100)) * 100;
                previous.right = (previous.right / (previous.span * 100)) * 100;
                
                continue;
            }
        }           
          
        return result;        
    };
    
    Plugin.prototype.render = function() {
        
        // render the table header
        var table = $('<table />').addClass('timetable');
        var thead = $('<thead />');
        var th_row = $('<tr />');
        
        thead.appendTo(table);
        th_row.appendTo(thead);
                
        var colcount = (this.options.max_hour - this.options.min_hour + 1);
        var hwidth = 100 / colcount;
        for (var h=this.options.min_hour; h <= this.options.max_hour; h++) {
            var hour = this.pad(h, 2) + ':00';
            th_row.append($('<th />').width(hwidth + '%').text(hour));   
        }
        
        // render the table
        var tbody = $('<tbody />');
        tbody.appendTo(table);
        
        // empoty rows are added between the timespans for easier styling
        var add_empty_row = function() {
            var empty_row = $('<tr />').addClass('empty_row');
            for (var i=0; i<colcount; i++) {
                empty_row.append($('<td />'));   
            }
            tbody.append(empty_row);
        };
             
        add_empty_row();
        
        // render a row for each timespan
        var plugin = this;
        $.each(this.options.data, function(index, timerow) {
            
            var row = $('<tr />');
            
            // add the columns
            $.each(plugin.merged_divisions(timerow.start, timerow.end), function(index, cell) {
                
                // ie 9+ does not understand colspan if added dynamically, only colSpan
                var td = $('<td />').attr('colSpan', cell.span);
                td.appendTo(row);

                var wrapper = $('<div />').addClass('timespan');
                wrapper.appendTo(td);
                
                var left = cell.left + '%';
                var middle = (100 - cell.left - cell.right) + '%';
                var right = cell.right + '%';               
                
                var occupied = $('<div />').addClass(cell.state).width(middle).css({
                    "margin-left": left,
                    "margin-right": right
                });
                
                if (plugin.options.show_text && cell.text) {
                    occupied.append($('<span />').text(cell.text));   
                }
                
                wrapper.append(occupied); 
            });
            
            tbody.append(row);
            
            add_empty_row();
        });                
        
        $(this.element).append(table);
    };
    
    // Pads the given number
    Plugin.prototype.pad = function(number, length) {
        var str = '' + number;
        while (str.length < length) {
            str = '0' + str;
        }
        return str;
    };

    $.fn[pluginName] = function ( options ) {
        return this.each(function () {
            if (!$.data(this, 'plugin_' + pluginName)) {
                $.data(this, 'plugin_' + pluginName, new Plugin( this, options ));
            }
        });
    };

})( jQuery, window, document );
    
(function($) {
    $(document).ready(function() {
        $('#placeholder').timetable({min_hour:6, max_hour:18, data:[ 
            {start: "08:15", end:"12:00"},
            {start: "08:30", end:"12:15"},
            {start: "08:45", end:"12:30"},
            {start: "09:00", end:"12:45"},
            {start: "05:00", end:"19:00"},
            {start: "15:00", end:"16:00"}
        ]});                        
    });
})(jQuery);