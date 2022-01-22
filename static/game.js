

/* Login Button */
document.getElementById('cta').addEventListener('click', function(e) {
    let login = document.getElementById('login').value


    document.getElementById('welcome').classList.add('hide')  // hide our welcome screen
    document.getElementById('screenwrapper').classList.remove('hide')  // reveal the main screen

    main()
})


// set our screen size based on actual browser size






function mkScreen() { 

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
        .domain(USURPENT.particles.map(d => d.color))
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


    // a group of paths for our particles
    const g = svg.append("g")
        .attr("fill", "none")
        .attr("stroke-linecap", "round")
        .attr("class", "particles")

    // and one for entities
    const gEnts = svg.append("g")
        .attr("fill", "none")
        .attr("stroke-linecap", "round")
        .attr("class", "entities")


    const randomcolor = d3.randomNormal(0, 1);






    // PARTICLES
    setInterval( function () {

        const t = performance.now();





        // color shifting just so we can see the tick happening
        USURPENT.particles = USURPENT.particles.map( particle => {

            particle.color = randomcolor();


        function rotate(cx, cy, x, y, angle) {
            var radians = (Math.PI / 180) * angle,
            cos = Math.cos(radians),
            sin = Math.sin(radians),
            nx = (cos * (x - cx)) + (sin * (y - cy)) + cx,
            ny = (cos * (y - cy)) - (sin * (x - cx)) + cy;
            return [nx, ny];
        }

            [particle.x, particle.y] = rotate(particle.target[0], particle.target[1], particle.x, particle.y, 13)

            return particle;

        })


        let parts = g.selectAll("path.particle")
            .data(USURPENT.particles, d => d.id )  // second arg to .data is a function to make a key

        // create
        parts.enter()
            .append('path')
                .attr('class', 'particle')
                .transition().duration(32)  // see tick speed below
                .attr("d", d => `M${x(d.x)},${y(d.y)}h0`)
                .attr("stroke", d => z(d.color))
                .attr("stroke-width", d => d.r * 3) 
                .attr('opacity', .61)



        // update
        parts
            .transition().duration(420)
            .attr("d", d => `M${x(d.x)},${y(d.y)}h0`)
            .attr("stroke", d => z(d.color)) 
            .attr('stroke-width', d => d.r )


        // remove
        parts.exit().remove();

    }, 100) // 33)  // for players we aim for 30fps, particles we can update less often


    // ENTITIES
    setInterval( function () { 

        // update coordinates based on last bearing / velocity

        USURPENT.entities = USURPENT.entities.map( ent => {

            // update position based on previous bearing

            ent.x += ent.bearing[0]
            ent.y += ent.bearing[1]

            return ent


        })



        let ents = gEnts.selectAll('path')
            .data(USURPENT.entities, d => d.id )


        // CREATE
        ents.enter().append('path')
            .attr('class', 'ent')
            .attr("d", d => `M${x(d.x)},${y(d.y)}h0`)
            .attr("stroke", d => z(d.color))
            .attr("stroke-width", 26)
            .attr('opacity', 1)


        // UPDATE
        ents
            .attr("d", d => `M${x(d.x)},${y(d.y)}h0`)
            .attr("stroke", d => z(d.color))


        // REMOVE
        ents.exit().remove();

    }, 33)  // aim for 33 fps


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

        let target = [x.invert(event.layerX), y.invert(event.layerY)]  // convert from paper space to model space

        USURPENT.entities.map( d=> {
            let delta_x = target[0] - d.x  
            let delta_y = target[1] - d.y
            let dist = Math.sqrt( delta_x**2 + delta_y**2 )



            // if a big move, cap / normalize our speeds
            if (dist > d.velocity) {

                // normalize vectors
                delta_x /= dist 
                delta_y /= dist // move towards the point with max speed of 1
            }


            let u = 5e-3 // something like a coefficient of friction.. better is to adjust actual velocity value ?

            delta_x *= u
            delta_y *= u

            // and if we've moved, update bearing
            if (dist > 1e-3) {

                d.bearing = [delta_x, delta_y]
                d.target = [...target]
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

    var particles, entities

    const random = d3.randomNormal(0, 1);  // random factory with a normal (Gaussian) distribution

    particles = Array.from({length: 13}, f => {
        out = {}
        out.id = uuidv4()
        out.target = [random(),random()]
        out.x = out.target[0] + random()
        out.y = out.target[1]
        out.r = (random() * 13)
        out.color = random()

        return out
    })

    entities = Array.from({length: 1}, f => {

        out = {}
        out.id = uuidv4()
        out.x = 0
        out.y = 0
        out.r = random()
        out.color = random()

        out.score = 1
        out.velocity = 1
        out.bearing = [0,0]

        return out

    })

    return {'particles':particles, 'entities': entities}

}






function main () {

    window.USURPENT = {...mkData()}

    mkScreen();

}
