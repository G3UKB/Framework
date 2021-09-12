// GenServer project main.go
package main

import (
	"fmt"
	"sync"
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
	g_s  GenServer
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

func gs_get_desc(name string) *Descriptor {
	d := Descriptor{}
	gs_lock()
	d, prs := gs_desc[name]
	gs_unlock()
	if prs {
		return &d
	} else {
		return &d
	}
}

// ====================================================================
// PUBLIC
// API
func callback(interface{}) {
	fmt.Println("Ballback...")
}

func gen_server(s string, f func(), c chan interface{}) {
	fmt.Println("GenServer...")
}

// ====================================================================
// PUBLIC
// Testing
func main() {
	gs_desc = make(map[string]Descriptor)
	d := Descriptor{}
	d.g_s = gen_server
	d.disp = callback
	d.ch = make(chan interface{})
	gs_store_desc("DESC", d)
	fmt.Println(gs_get_desc("DESC"))
}
