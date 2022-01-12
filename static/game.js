

/* Login Button */
document.getElementById('cta').addEventListener('click', function(e) {
    let login = document.getElementById('login').value

    document.getElementById('welcome').classList.add('hide')
    document.getElementById('screenwrapper').classList.remove('hide')
    console.log(this, e)
})


// set our screen size based on actual browser size

var bounds = {}

function setBounds() {

    bounds.x = screen.availHeight;
    bounds.y = screen.availWidth;

}

window.addEventListener('resize', setBounds)