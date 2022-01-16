

/* Login Button */
document.getElementById('cta').addEventListener('click', function(e) {
    let login = document.getElementById('login').value


    document.getElementById('welcome').classList.add('hide')  // hide our welcome screen
    document.getElementById('screenwrapper').classList.remove('hide')  // reveal the main screen

    main()
})


// set our screen size based on actual browser size






function chart(data) { 
    window.data = data;

    const svg = d3.select('svg')

    var bounds = {}

    function setBounds() {

        let screen = document.getElementById('screen')

        bounds.height = screen.clientHeight;
        bounds.width = screen.clientWidth;

    }

    // calculate the bounds of our SVG element
    setBounds()

    // listen for a browser resize to adjust
    window.addEventListener('resize', setBounds)


    const k = bounds.height / bounds.width;
    const x = d3.scaleLinear()
        .domain([-3, 3])
        .range([0, bounds.width])

    const y = d3.scaleLinear()
        .domain([-3 * k, 3 * k])
        .range([bounds.height, 0])

    const z = d3.scaleOrdinal()
        .domain(data.map(d => d.color))
        .range(d3.schemeCategory10)


    const gx = svg.append("g")
        .attr('transform', `translate(0, ${bounds.height -1})`)
        .call(
            d3.axisTop(x).ticks(5) 
        )
    const gy = svg.append("g")
        .call(
            d3.axisRight(y).ticks(3)
        )                                                                                                       


    // a group of paths for our circles
    const g = svg.append("g")
      .attr("fill", "none")
      .attr("stroke-linecap", "round");




    setInterval( function () {
    // 0 length paths are supposed to be more performant than circles

            var ents = g.selectAll("path")
        .data(window.data) // , d => d.uuid )  // second arg to .data is a function to make a key

            // on creation
        ents.enter()
            .append('path')
                .transition().duration(250)
                .attr("d", d => `M${x(d.x)},${y(d.y)}h0`)
                .attr("stroke", d => z(d.color))
                .attr("stroke-width", 13)
                .attr('opacity', .61)



        // update
        ents
            .transition().duration(250)
            .attr("d", d => `M${x(d.x)},${y(d.y)}h0`)
            .attr("stroke", d => z(d.id))  // will size change?


        // remove
        ents.exit().remove();

    }, 150)


    svg.on('click', function(event,d) {

        pt = [x.invert(event.layerX), y.invert(event.layerY)]  // cast our coordinates to model space

        window.data.map( d=> {
            let delta_x = pt[0] - d.x
            let delta_y = pt[1] - d.y
            let dist = Math.sqrt( delta_x**2 + delta_y**2 )

            // normalize vectors
            d.x += Math.min(delta_x, delta_x / dist) || 0
            d.y += Math.min(delta_y, delta_y / dist) || 0  // move towards the point with max speed of 1
            return d 
        })
        console.log(pt)

    })


    document.onmousemove = handleMouseMove;
    function handleMouseMove(event) {
      var eventDoc, doc, body, pageX, pageY;
      
      event = event || window.event; // IE-ism
      
      // If pageX/Y aren't available and clientX/Y
      // are, calculate pageX/Y - logic taken from jQuery
      if (event.pageX == null && event.clientX != null) {
        eventDoc = (event.target && event.target.ownerDocument) || document;
        doc = eventDoc.documentElement;
        body = eventDoc.body;

        event.pageX = event.clientX +
          (doc && doc.scrollLeft || body && body.scrollLeft || 0) -
          (doc && doc.clientLeft || body && body.clientLeft || 0);
        event.pageY = event.clientY +
          (doc && doc.scrollTop  || body && body.scrollTop  || 0) -
          (doc && doc.clientTop  || body && body.clientTop  || 0 );
      }

        let target = [x.invert(event.layerX), y.invert(event.layerY)]

        window.data.map( d=> {
            let delta_x = target[0] - d.x  
            let delta_y = target[1] - d.y
            let dist = Math.sqrt( delta_x**2 + delta_y**2 )

            // if a big move, cap / normalize our speeds
            if (dist > 1) {

                console.log(dist,delta_x, delta_y)
                // normalize vectors
                delta_x /= dist
                delta_y /= dist // move towards the point with max speed of 1
            }

            // and if we've moved, update positions
            if (dist > 1e-3) {

                d.x += delta_x 
                d.y += delta_y 
            }

            return d 
        })

    }
}


function uuidv4() {
  return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
    (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
  );
}


function mkData() {

    const random = d3.randomNormal(0, 1);

    return Array.from({length: 13}, f => {
        out = {}
        out.id = uuidv4()
        out.x = random()
        out.y = random()
        out.color = random()

        return out
    })


  const sqrt3 = Math.sqrt(3);
  return [].concat(
    Array.from({length: 300}, () => [random() + sqrt3, random() + 1, 0]),
    Array.from({length: 300}, () => [random() - sqrt3, random() + 1, 1]),
    Array.from({length: 300}, () => [random(), random() - 1, 2])
  );
}






function main () {

    chart(mkData())

}
