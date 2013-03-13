//extend underscore.js with utilities
_.mixin({
    parse_date: function(isodate) {
        var parse = function(str) { return parseInt(str, 10); };
        var values = _.map(isodate.split('-'), parse);

        return {year:values[0], month:values[1], day:values[2]};
    },
    assert: function(condition, message) {
        if (!condition) throw new Error(message);
    }
});