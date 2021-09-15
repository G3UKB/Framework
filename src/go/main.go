// GenServer project main.go
package main

import (
	"fmt"
	"sync"
	"time"
	//"github.com/alexpantyukhin/go-pattern-match"
)

// ====================================================================
// PRIVATE
// Task dictionary
// This will be accessed from multiple threads
//
// Holds refs in the form {name: [gen-server, dispatcher, queue]}
type GenServer func(string, func(), chan interface{})
type Dispatcher func(interface{})
type Descriptor struct {
	disp Dispatcher
	ch   chan interface{}
}

var gs_desc map[string]Descriptor

// Task dict lock
var gs_mu sync.Mutex

func gs_lock() {
	gs_mu.Lock()
}

func gs_unlock() {
	gs_mu.Unlock()
}

func gs_store_desc(name string, desc Descriptor) {
	gs_lock()
	gs_desc[name] = desc
	gs_unlock()
}

func gs_get_desc(name string) (bool, Descriptor) {
	d := Descriptor{}
	gs_lock()
	d, prs := gs_desc[name]
	gs_unlock()
	if prs {
		return true, d
	} else {
		return false, d
	}
}

func gs_get_all_desc() []Descriptor {
	d := []Descriptor{}
	gs_lock()
	for _, desc := range gs_desc {
		d = append(d, desc)
	}
	gs_unlock()
	return d
}

func gs_rm_desc(name string) {
	gs_lock()
	_, prs := gs_desc[name]
	if prs {
		delete(gs_desc, name)
	}
	gs_unlock()
}

// ====================================================================
// PUBLIC
// API
func gs_new(name string, f Dispatcher) {
	// Make a channel
	ch := make(chan interface{})
	// Create and run a new gen server
	go gen_server(name, f, ch)
	// Add to registry
	d := Descriptor{}
	d.disp = f
	d.ch = ch
	gs_store_desc(name, d)
}

func gs_term(name string) {
	prs, d := gs_get_desc(name)
	if prs {
		d.ch <- "quit"
	}
}

func gs_term_all() {
	descs := gs_get_all_desc()
	for _, d := range descs {
		d.ch <- "quit"
	}
}

func gs_msg(name string, msg interface{}) {
	prs, d := gs_get_desc(name)
	if prs {
		d.ch <- msg
	}
}

// ====================================================================
// PRIVATE
// The gen-server task
func gen_server(s string, f Dispatcher, c chan interface{}) {
	fmt.Println("GenServer ", s)
	for {
		msg := <-c
		fmt.Println(msg)
		// Can't figure how this works
		// Probably give up on Go at this point
		//isMatched, mr := match.Match(msg).
		//	When("quit", {break}).
		//	Result()
		if msg == "quit" {
			break
		}
		time.Sleep(time.Second * 1)
	}
	fmt.Println("GenServer exiting ... ", s)
}

// ====================================================================
// PUBLIC
// Testing
func callback(interface{}) {
	fmt.Println("Callback...")
}

func main() {
	gs_desc = make(map[string]Descriptor)
	//d := Descriptor{}
	//d.disp = callback
	//d.ch = make(chan interface{})
	//gs_store_desc("DESC", d)
	//fmt.Println(gs_get_desc("DESC"))
	//fmt.Println(gs_get_all_desc())
	//gs_rm_desc("DESC")
	//fmt.Println(gs_get_all_desc())

	gs_new("REAL", callback)
	var input string
	fmt.Scanln(&input)
	fmt.Println(gs_get_all_desc())
	gs_term("REAL")
	fmt.Scanln(&input)
}
