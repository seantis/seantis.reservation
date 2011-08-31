from datetime import timedelta

def is_valid_raster(raster):
    return raster in (5, 10, 15, 30, 60)

def rasterize_start(date, raster):
    assert(is_valid_raster(raster))

    delta = timedelta(minutes=date.minute % raster, 
                      seconds=date.second, 
                      microseconds=date.microsecond)
    
    return date - delta

def rasterize_end(date, raster):
    if date.minute % raster:
        date = rasterize_start(date, raster)
        delta = timedelta(microseconds=-1, minutes=raster)
    else:
        delta = timedelta(microseconds=-1)
    return date + delta

def rasterize_span(start, end, raster):
    return rasterize_start(start, raster), rasterize_end(end, raster)

def iterate_span(start, end, raster):
    start, end = rasterize_span(start, end, raster)

    step = start
    while (step <= end):
        yield step, step + timedelta(microseconds=-1, minutes=raster)
        step += timedelta(seconds=raster*60)