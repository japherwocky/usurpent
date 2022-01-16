

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
            .data(window.data, (d,i) => i )  // second arg to .data is a function to make a key

            // on creation
        ents.enter()
            .append('path')
                .transition().duration(250)
                .attr("d", d => `M${x(d.x)},${y(d.y)}h0`)
                .attr("stroke", d => z(d.color))
                .attr("stroke-width", 13)
                .attr('opacity', .39)



        // update
        ents
            .transition().duration(250)
            .attr("d", d => `M${x(d.x)},${y(d.y)}h0`)
            .attr("stroke", d => z(d.id))  // will size change?


        // remove
        ents.exit().remove();

    }, 250)


    svg.on('click', function(event,d) {

        pt = [x.invert(event.x), y.invert(event.y)]  // cast our coordinates to model space

        window.data.map( d=> {
            let delta_x = pt[0] - d.x
            let delta_y = pt[1] - d.y
            let dist = Math.sqrt( delta_x**2 + delta_y**2 )

            d.x += delta_x / dist
            d.y += delta_y / dist
            return d 
        })
        console.log(pt)

    })



}


function uuidv4() {
  return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
    (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
  );
}


function mkData() {

    const random = d3.randomNormal(0, 1);

    return Array.from({length: 300}, f => {
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
