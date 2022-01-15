

/* Login Button */
document.getElementById('cta').addEventListener('click', function(e) {
    let login = document.getElementById('login').value


    document.getElementById('welcome').classList.add('hide')  // hide our welcome screen
    document.getElementById('screenwrapper').classList.remove('hide')  // reveal the main screen

    main()
})


// set our screen size based on actual browser size

var bounds = {}

function setBounds() {

    bounds.height = screen.availHeight;
    bounds.width = screen.availWidth;

}

setBounds()
window.addEventListener('resize', setBounds)




function chart(data) { 


    window.data = data;

    const zoom = d3.zoom()
      .on("zoom", zoomed);

    const k = bounds.height / bounds.width;

    const x = d3.scaleLinear()
        .domain([-4.5, 4.5])
        .range([0, bounds.width])
    window.x = x;

    const y = d3.scaleLinear()
        .domain([-4.5 * k, 4.5 * k])
        .range([bounds.height, 0])

    const z = d3.scaleOrdinal()
        .domain(data.map(d => d[2]))
        .range(d3.schemeCategory10)


    const xAxis = (g, x) => g
        .attr("transform", `translate(0,${bounds.height})`)
        .call(d3.axisTop(x).ticks(12))
        .call(g => g.select(".domain").attr("display", "none"))

    const yAxis = (g, y) => g
        .call(d3.axisRight(y).ticks(12 * k))
        .call(g => g.select(".domain").attr("display", "none"))    



    // Our zoom locations ?
    function mkTransforms(data) {
        const transforms = [["Overview", d3.zoomIdentity]]  // a list of tuples, the base is the reset zoom function

            .concat(d3.groups(data, d => d[2])  
                .map(([key, data]) => {
            const [x0, x1] = d3.extent(data, d => d[0]).map(x);
            const [y1, y0] = d3.extent(data, d => d[1]).map(y);
            const k = 0.9 * Math.min(bounds.width / (x1 - x0), bounds.height / (y1 - y0));
            const tx = (bounds.width - k * (x0 + x1)) / 2;
            const ty = (bounds.height - k * (y0 + y1)) / 2;
            return [`Cluster ${key}`, d3.zoomIdentity.translate(tx, ty).scale(k)];
        }))


        return transforms;
    }

    const tform = mkTransforms(data)
    window.tform = tform;

                                                                                                                 




  const svg = d3.select('svg')

  const g = svg.append("g")
      .attr("fill", "none")
      .attr("stroke-linecap", "round");

  g.selectAll("path")
    .data(data)
    .join("path")
      .attr("d", d => `M${x(d[0])},${y(d[1])}h0`)
      .attr("stroke", d => z(d[2]));

  const gx = svg.append("g");

  const gy = svg.append("g");

  // svg.call(zoom.transform, tform);
  svg.call(zoom.transform, tform[0][1])

  function zoomed(event) {
    let {transform} = event;
    debugger;
    // console.log(transform);
    g.attr("transform", transform).attr("stroke-width", 5 / k);
    gx.call(xAxis, transform.rescaleX(x));
    gy.call(yAxis, transform.rescaleY(y));
  }

  window.screen = Object.assign(svg.node(), {
    update(transform) {
      svg.transition()
          .duration(1500)
          .call(zoom.transform, transform);
    }
  });

}

function mkData() {
  const random = d3.randomNormal(0, 0.2);
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
